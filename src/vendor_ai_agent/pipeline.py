"""High-level orchestration for the Tender Vendor AI Agent."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

from .config import RuntimeConfig, paths
from .contracts import (
    CapabilityMatcherContract,
    DocumentParserContract,
    OutputGeneratorContract,
    RequirementExtractorContract,
    VendorDiscoveryContract,
    VendorEnricherContract,
    VendorFilterContract,
)
from .ingestion import TenderIngestionRouter
from .ingestion.models import TenderIngestionRequest
from .models import (
    PipelineArtifacts,
    TenderProfile,
    TenderSection,
    VendorMatchResult,
    VendorRecord,
    ContactInfo,
)
from .modules import (
    CapabilityMatcher,
    DocumentFetcher,
    DocumentParser,
    MetadataBackfill,
    OpenAIProvider,
    OutputGenerator,
    RequirementExtractor,
    VendorDiscovery,
    VendorFilter,
)
from .modules.enrichment import VendorEnricher
from .modules.http_client import HttpClientFactory
from .modules.llm_providers import AsyncOpenAIProvider, OpenAIProvider, WebsiteContentProvider


from .sources.sam_entity import SamEntitySource
from .sources import CanadaContractsVendorSource, StaticDirectorySource, ApolloSearchSource, SerperVendorSource
from .database.connection import get_session
from .enrichment_providers import AsyncWebsiteContentProvider

@dataclass
class PipelineContext:
    config: RuntimeConfig
    document_parser: DocumentParserContract
    document_fetcher: DocumentFetcher
    requirement_extractor: RequirementExtractorContract
    vendor_discovery: VendorDiscoveryContract
    vendor_enricher: VendorEnricherContract
    vendor_filter: VendorFilterContract
    capability_matcher: CapabilityMatcherContract
    output_generator: OutputGeneratorContract
    ingestion_router: TenderIngestionRouter
    metadata_backfill: MetadataBackfill


class TenderVendorPipeline:
    """Coordinates all modules to produce final vendor recommendations."""

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        cfg = config or RuntimeConfig()
        
        self.llm_provider = None
        use_async_llm = cfg.capability_matching.enable_llm_assessment
        
        try:
            if use_async_llm:
                from .modules.llm_providers import AsyncOpenAIProvider
                self.llm_provider = AsyncOpenAIProvider(
                    default_model=cfg.llm.cheap_model,
                    use_flex_tier=cfg.llm.use_flex_tier,
                    concurrency_limit=100  # Optimized: 5x increase for parallel LLM processing
                )
                logging.info("Async LLM provider initialized with model: %s", cfg.llm.cheap_model)
            else:
                self.llm_provider = OpenAIProvider(
                    default_model=cfg.llm.cheap_model,
                    use_flex_tier=cfg.llm.use_flex_tier
                )
                logging.info("Sync LLM provider initialized with model: %s", cfg.llm.cheap_model)
        except (ImportError, ValueError) as exc:
            logging.warning("LLM provider not available: %s. Using fallback mode.", exc)
        
        # Initialize sources
        sam_source = SamEntitySource(
            api_key=cfg.sam_api.api_key,
            sync_to_db=True
        )
        
        sources = [sam_source]
        
        try:
            canada_source = CanadaContractsVendorSource()
            sources.append(canada_source)
            logging.info("Canada Contracts source initialized successfully")
        except Exception as exc:
            logging.warning("Failed to initialize Canada Contracts source: %s", exc)

        if cfg.discovery.enable_apollo_discovery and cfg.apollo_api_key:
            try:
                apollo_source = ApolloSearchSource(
                    api_key=cfg.apollo_api_key,
                    max_pages=cfg.discovery.apollo_max_pages
                )
                sources.append(apollo_source)
                logging.info("Apollo primary discovery source initialized successfully")
            except Exception as exc:
                logging.warning("Failed to initialize Apollo discovery source: %s", exc)
        elif cfg.discovery.enable_serper_discovery and cfg.serper_api_key:
            try:
                serper_source = SerperVendorSource(
                    api_key=cfg.serper_api_key,
                    query_limit=cfg.discovery.serper_discovery_query_limit,
                    config=cfg
                )
                sources.append(serper_source)
                logging.info("Serper discovery source initialized successfully")
            except Exception as exc:
                logging.warning("Failed to initialize Serper discovery source: %s", exc)

        # Always register the static directory as a resilience fallback so tests and
        # offline environments still yield candidate vendors.
        sources.append(StaticDirectorySource())
        logging.debug("StaticDirectorySource registered as fallback vendor provider")
        
        # Initialize enrichment providers
        enrichment_providers = []
        
        if cfg.enrichment.enable_website_search and cfg.serper_api_key:
            from .enrichment_providers import HybridWebsiteEnricher
            website_enricher = HybridWebsiteEnricher(
                serper_api_key=cfg.serper_api_key,
                enable_ddg=cfg.enrichment.enable_ddg_search,
                enable_serper_fallback=cfg.enrichment.enable_serper_fallback,
                min_confidence=cfg.enrichment.website_search_min_confidence
            )
            enrichment_providers.append(website_enricher)
            logging.info("HybridWebsiteEnricher registered for website discovery")
        
        if cfg.capability_matching.enable_website_scraping:
            website_provider = AsyncWebsiteContentProvider(
                enable_cache=True,
                enable_logging=True,
                enable_playwright_fallback=cfg.enrichment.enable_playwright_fallback,
                playwright_max_contexts=cfg.enrichment.playwright_max_contexts,
                playwright_wait_ms=cfg.enrichment.playwright_wait_ms,
            )
            enrichment_providers.append(website_provider)
            logging.info("AsyncWebsiteContentProvider registered for enrichment")
        
        if cfg.enrichment.enable_contact_scraping and cfg.serper_api_key:
            from .enrichment_providers import ContactScrapingProvider, SerperClient, SmartEmailGeneratorProvider
            
            serper_client = SerperClient(api_key=cfg.serper_api_key)
            
            smart_email_generator = None
            if cfg.enrichment.enable_smart_email_generation:
                smart_email_generator = SmartEmailGeneratorProvider(
                    serper_client=serper_client,
                    enable_mx_check=cfg.enrichment.smart_email_enable_mx_check,
                    enable_serper_validation=cfg.enrichment.smart_email_serper_validation,
                    prefixes=cfg.enrichment.smart_email_prefixes,
                    max_candidates=cfg.enrichment.smart_email_max_candidates,
                    require_company_context=cfg.enrichment.smart_email_require_company_context,
                    min_confidence=cfg.enrichment.smart_email_min_confidence,
                )
                logging.info("SmartEmailGeneratorProvider initialized for Level 4 fallback")
            
            contact_provider = ContactScrapingProvider(
                llm_provider=self.llm_provider,
                scraper_timeout=cfg.enrichment.scraper_timeout_seconds,
                enable_llm_fallback=cfg.enrichment.enable_llm_fallback,
                serper_client=serper_client,
                enable_targeted_serper=cfg.enrichment.enable_targeted_serper_fallback,
                enable_playwright_fallback=cfg.enrichment.enable_playwright_fallback,
                playwright_max_contexts=cfg.enrichment.playwright_max_contexts,
                playwright_wait_ms=cfg.enrichment.playwright_wait_ms,
                enable_smart_email=cfg.enrichment.enable_smart_email_generation,
                smart_email_generator=smart_email_generator,
            )
            enrichment_providers.append(contact_provider)
            logging.info("ContactScrapingProvider registered with 4-level fallback")
        
        self.context = PipelineContext(
            config=cfg,
            document_parser=DocumentParser(),
            document_fetcher=DocumentFetcher(),
            requirement_extractor=RequirementExtractor(llm_provider=self.llm_provider),
            vendor_discovery=VendorDiscovery(sources=sources),
            vendor_enricher=VendorEnricher(
                providers=enrichment_providers,
                max_workers=cfg.enrichment.max_enrichment_workers,
                batch_size=cfg.enrichment.batch_size,
                min_batch_success_rate=cfg.enrichment.min_batch_success_rate,
                max_enrichment_batches=cfg.enrichment.max_enrichment_batches,
                target_relevant_vendors=cfg.filtering.max_candidates,
                enable_batch_quality_gates=cfg.enrichment.enable_batch_quality_gates,
                enable_sampling_fallback=cfg.enrichment.enable_sampling_fallback,
                sample_positions=cfg.enrichment.sample_positions,
                relevance_score_threshold=cfg.enrichment.relevance_score_threshold
            ),
            vendor_filter=VendorFilter(config=cfg.filtering),
            capability_matcher=CapabilityMatcher(llm_provider=self.llm_provider, config=cfg.capability_matching),
            output_generator=OutputGenerator(),
            ingestion_router=TenderIngestionRouter.from_config(cfg),
            metadata_backfill=MetadataBackfill(),
        )

    def run(
        self,
        tender_files: Iterable[Path],
        *,
        ingestion_request: Optional[TenderIngestionRequest] = None,
        disable_auto_ingestion: bool = False,
    ) -> PipelineArtifacts:
        """Run the pipeline with resource cleanup."""
        try:
            return self._run_internal(
                tender_files,
                ingestion_request=ingestion_request,
                disable_auto_ingestion=disable_auto_ingestion
            )
        finally:
            self.cleanup()

    def _run_internal(
        self,
        tender_files: Iterable[Path],
        *,
        ingestion_request: Optional[TenderIngestionRequest] = None,
        disable_auto_ingestion: bool = False,
    ) -> PipelineArtifacts:
        file_list = [Path(path) for path in tender_files]
        sections = self.context.document_parser.parse(file_list)
        tender_profile = self.context.requirement_extractor.extract(sections)

        should_auto_ingest = (
            self.context.config.enable_auto_ingestion
            and not disable_auto_ingestion
            and ingestion_request is None
        )
        request_to_use = ingestion_request
        if should_auto_ingest:
            request_to_use = self._build_auto_ingestion_request(tender_profile)
        
        auto_generated = ingestion_request is None and request_to_use is not None
        if request_to_use:
            tender_profile, sections = self._hydrate_from_ingestion(
                request_to_use, file_list, auto_generated=auto_generated
            )
        
        cfg = self.context.config
        use_cache = cfg.discovery.enable_batch_cache
        processing_batch = max(1, cfg.discovery.processing_batch)
        cached_bundle = None
        filtered_vendors: Optional[List[VendorRecord]] = None
        filtered_from_cache = False
        cached_processed_batches: List[int] = []

        if use_cache and processing_batch > 1:
            cached_bundle = self._load_cached_vendors(tender_profile)
            if cached_bundle:
                filtered_vendors = cached_bundle.get("vendors", [])
                cached_processed_batches = cached_bundle.get("processed_batches", [])
                filtered_from_cache = True
                logging.info(
                    "Loaded %s cached vendors for batch %s",
                    len(filtered_vendors),
                    processing_batch,
                )

        if filtered_vendors is None:
            try:
                discovered_vendors = self.context.vendor_discovery.discover(tender_profile)
            except Exception as e:
                raise Exception(f"Vendor discovery failed: {e}")

            self._log_discovery_metrics(discovered_vendors)

            discovered_vendors = self._maybe_run_serper_discovery(
                tender_profile, discovered_vendors
            )

            discovered_vendors = self._maybe_run_apollo_booster(
                tender_profile, discovered_vendors
            )

            if not discovered_vendors:
                logging.warning(
                    "Vendor discovery returned no candidates; generating fallback directory vendors"
                )
                fallback_source = StaticDirectorySource()
                discovered_vendors = fallback_source.search(tender_profile)
                self._log_discovery_metrics(discovered_vendors, note="fallback_static")

            filtered_vendors = self.context.vendor_filter.filter(
                tender_profile, discovered_vendors
            )
            filtering_metrics = self.context.vendor_filter.get_metrics()
            self._log_filtering_metrics(filtering_metrics)

            filtered_vendors = self._ensure_min_candidates_after_filter(
                tender_profile, filtered_vendors
            )

            if use_cache:
                self._write_vendor_cache(tender_profile, filtered_vendors)
        else:
            discovered_vendors = filtered_vendors
            filtering_metrics = None
        
        batch_vendors, batch_info = self._select_batch_vendors(
            filtered_vendors,
            cached_processed_batches,
        )

        if not batch_vendors:
            logging.warning(
                "Batch %s returned no vendors to process",
                batch_info["batch_id"],
            )
            return PipelineArtifacts(
                tender_sections=sections,
                tender_profile=tender_profile,
                raw_vendors=filtered_vendors,
                enriched_vendors=[],
                filtered_vendors=[],
                filtering_metrics=filtering_metrics,
                final_matches=[],
                all_matches=[],
                batch_id=batch_info["batch_id"],
                processed_batches=batch_info["processed_batches"],
            )

        all_scored_matches: List[VendorMatchResult]
        
        from .modules.llm_providers import AsyncOpenAIProvider
        use_async = (
            hasattr(self.context.vendor_enricher, 'enrich_with_scoring_async')
            and hasattr(self.context.capability_matcher, 'score_async')
            and isinstance(self.llm_provider, AsyncOpenAIProvider)
        )
        
        if use_async:
            logging.info("Using async pipeline for enrichment + scoring")
            try:
                try:
                    loop = asyncio.get_running_loop()
                    logging.debug("Detected existing event loop (Streamlit), using run_until_complete")
                    (
                        enriched_vendors,
                        relevant_matches,
                        all_scored_matches,
                    ) = loop.run_until_complete(
                        self.context.vendor_enricher.enrich_with_scoring_async(
                            profile=tender_profile,
                            vendors=batch_vendors,
                            scoring_fn_async=self.context.capability_matcher.score_async,
                        )
                    )
                except RuntimeError:
                    logging.debug("No event loop detected, using asyncio.run()")
                    (
                        enriched_vendors,
                        relevant_matches,
                        all_scored_matches,
                    ) = asyncio.run(
                        self.context.vendor_enricher.enrich_with_scoring_async(
                            profile=tender_profile,
                            vendors=batch_vendors,
                            scoring_fn_async=self.context.capability_matcher.score_async,
                        )
                    )
                matches = (
                    relevant_matches if relevant_matches else all_scored_matches
                )
            except Exception as exc:
                logging.warning(f"Async pipeline failed, falling back to sync: {exc}")
                use_async = False
        
        if not use_async:
            if hasattr(self.context.vendor_enricher, 'enrich_with_scoring'):
                (
                    enriched_vendors,
                    relevant_matches,
                    all_scored_matches,
                ) = self.context.vendor_enricher.enrich_with_scoring(
                    profile=tender_profile,
                    vendors=batch_vendors,
                    scoring_fn=self.context.capability_matcher.score,
                )
                matches = (
                    relevant_matches if relevant_matches else all_scored_matches
                )
            else:
                enriched_vendors = self.context.vendor_enricher.enrich(batch_vendors)
                all_scored_matches = self.context.capability_matcher.score(
                    tender_profile, enriched_vendors
                )
                matches = all_scored_matches

        self._annotate_match_status(
            all_scored_matches,
            threshold=self.context.vendor_enricher.relevance_score_threshold,
            batch_id=batch_info["batch_id"],
        )

        self._log_enrichment_metrics(enriched_vendors)
        self._log_matching_metrics(self.context.capability_matcher)

        if use_cache:
            self._update_cache_batches(
                tender_profile,
                batch_info["processed_batches"]
                + ([batch_info["batch_id"]]
                   if batch_info["batch_id"]
                   not in batch_info["processed_batches"]
                   else []),
            )
        processed_batches_view = sorted(
            set(batch_info["processed_batches"] + [batch_info["batch_id"]])
        )

        return PipelineArtifacts(
            tender_sections=sections,
            tender_profile=tender_profile,
            raw_vendors=filtered_vendors,
            enriched_vendors=enriched_vendors,
            filtered_vendors=batch_vendors,
            filtering_metrics=filtering_metrics,
            final_matches=matches,
            all_matches=all_scored_matches,
            batch_id=batch_info["batch_id"],
            processed_batches=processed_batches_view,
        )

    def cleanup(self) -> None:
        """Cleanup pipeline resources."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # If loop is running, schedule cleanup
                loop.create_task(HttpClientFactory.close())
            else:
                # If loop is closed/not running, run synchronously
                loop.run_until_complete(HttpClientFactory.close())
        except RuntimeError:
            # No event loop
            asyncio.run(HttpClientFactory.close())
        except Exception as e:
            logging.warning(f"Error cleaning up pipeline resources: {e}")

    def _hydrate_from_ingestion(
        self,
        request: TenderIngestionRequest,
        initial_files: List[Path],
        *,
        auto_generated: bool = False,
    ) -> tuple[TenderProfile, List[TenderSection]]:
        try:
            ingestion_result = self.context.ingestion_router.ingest(request)
        except Exception as exc:
            if not auto_generated:
                raise
            logging.warning("Auto ingestion failed, using local files only: %s", exc)
            sections = self.context.document_parser.parse(initial_files)
            profile = self.context.requirement_extractor.extract(sections)
            return profile, sections

        tender_id = request.reference_number or request.solicitation_number
        base_profile = TenderProfile(
            tender_id=tender_id,
            country=request.country,
            source_system=request.source_system,
            api_metadata=ingestion_result.api_metadata,
        )
        attachments = self.context.document_fetcher.fetch(ingestion_result.attachments)
        files_with_attachments = initial_files + attachments
        sections = self.context.document_parser.parse(files_with_attachments)
        profile = self.context.requirement_extractor.extract(sections, base_profile=base_profile)
        profile = self.context.metadata_backfill.backfill(profile)
        return profile, sections

    def _build_auto_ingestion_request(
        self, profile: TenderProfile
    ) -> Optional[TenderIngestionRequest]:
        reference = profile.doc_extracted.structured.reference_number
        if reference:
            return TenderIngestionRequest(
                country="CAN",
                source_system="CANADABUYS",
                reference_number=reference,
            )
        return None

    def save_outputs(
        self,
        matches: List[VendorMatchResult],
        *,
        base_name: str = "tender_vendors",
        directory: Optional[Path] = None,
    ) -> None:
        output_dir = directory or paths.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_config = self.context.config.output
        final_name = base_name or output_config.base_filename

        if output_config.include_xlsx:
            self.context.output_generator.to_excel(matches, output_dir / f"{final_name}.xlsx")
        if output_config.include_csv:
            self.context.output_generator.to_csv(matches, output_dir / f"{final_name}.csv")
        if output_config.include_json:
            self.context.output_generator.to_json(matches, output_dir / f"{final_name}.json")

    def _maybe_run_serper_discovery(
        self,
        profile: TenderProfile,
        vendors: List[VendorRecord],
    ) -> List[VendorRecord]:
        cfg = self.context.config
        
        GOVERNMENT_SOURCES = {
            "sam_entity", 
            "canada_contracts", 
            "canada_award_notices",
            "canada_odbus", 
            "canada_pspc_payments", 
            "canada_sosa"
        }
        
        max_candidates = cfg.filtering.max_candidates
        max_govt_vendors = int(max_candidates * cfg.discovery.max_government_source_percentage)
        
        govt_vendors = [v for v in vendors if v.source in GOVERNMENT_SOURCES]
        non_govt_vendors = [v for v in vendors if v.source not in GOVERNMENT_SOURCES]
        
        if len(govt_vendors) > max_govt_vendors:
            logging.info(
                "Government vendors exceed cap: %s > %s (%.0f%% limit). "
                "Cutting to %s government vendors.",
                len(govt_vendors),
                max_govt_vendors,
                cfg.discovery.max_government_source_percentage * 100,
                max_govt_vendors,
            )
            govt_vendors = govt_vendors[:max_govt_vendors]
        
        vendors = govt_vendors + non_govt_vendors
        current_count = len(vendors)
        deficit = max(0, max_candidates - current_count)
        
        should_use_serper = (
            cfg.discovery.enable_serper_discovery
            and cfg.serper_api_key
            and deficit > 0
        )
        
        if not should_use_serper:
            if current_count >= max_candidates:
                logging.info(
                    "Serper discovery skipped: %s vendors >= max_candidates %s",
                    current_count,
                    max_candidates,
                )
            return vendors

        logging.info(
            "Serper discovery triggered: %s vendors, need %s more to reach %s",
            current_count,
            deficit,
            max_candidates,
        )
        
        try:
            seen_domains = set()
            for v in vendors:
                domain = v.filtering_metadata.get('serper_domain') or v.filtering_metadata.get('domain')
                if domain:
                    seen_domains.add(domain.lower())
            
            serper_source = SerperVendorSource(
                api_key=cfg.serper_api_key,
                query_limit=cfg.discovery.serper_max_queries,
                config=cfg
            )
            serper_vendors = serper_source.search(
                profile, 
                target_count=deficit,
                seen_domains=seen_domains
            )
            if serper_vendors:
                self._log_discovery_metrics(serper_vendors, note="serper_primary")
                vendors = vendors + serper_vendors
                logging.info(
                    "After Serper: %s total vendors (%s added)",
                    len(vendors),
                    len(serper_vendors),
                )
        except Exception as exc:
            logging.warning("Serper fallback failed: %s", exc)
        
        return vendors

    def _maybe_run_apollo_booster(
        self,
        profile: TenderProfile,
        vendors: List[VendorRecord],
    ) -> List[VendorRecord]:
        cfg = self.context.config
        should_boost = (
            cfg.discovery.enable_apollo_booster
            and cfg.apollo_api_key
            and len(vendors) < cfg.discovery.apollo_min_candidates
        )
        if not should_boost:
            return vendors

        logging.info(
            "Apollo booster enabled: %s vendors < min %s, fetching additional candidates",
            len(vendors),
            cfg.discovery.apollo_min_candidates,
        )
        booster = ApolloSearchSource(
            api_key=cfg.apollo_api_key,
            max_pages=cfg.discovery.apollo_max_pages,
        )
        apollo_vendors = booster.search(profile)
        if apollo_vendors:
            self._log_discovery_metrics(apollo_vendors, note="apollo_booster")
            vendors = vendors + apollo_vendors
        return vendors

    def _ensure_min_candidates_after_filter(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> List[VendorRecord]:
        cfg = self.context.config
        min_candidates = cfg.discovery.min_relevant_candidates
        if len(vendors) >= min_candidates:
            return vendors

        logging.info(
            "Post-filter candidates below target (%s < %s). Fetching additional vendors via Serper/Apollo.",
            len(vendors),
            min_candidates,
        )

        vendors = self._maybe_run_serper_discovery(profile, vendors)
        if len(vendors) >= min_candidates:
            return vendors

        vendors = self._maybe_run_apollo_booster(profile, vendors)
        return vendors

    def _log_discovery_metrics(self, vendors: List[VendorRecord], note: str | None = None) -> None:
        from collections import Counter

        total = len(vendors)
        if total == 0:
            logging.info("[Discovery] no vendors discovered%s",
                         f" ({note})" if note else "")
            return
        counts = Counter(v.source or "unknown" for v in vendors)
        logging.info("[Discovery] %s vendors (by source: %s)%s",
                     total,
                     ", ".join(f"{src}:{cnt}" for src, cnt in counts.items()),
                     f" ({note})" if note else "")

    def _log_filtering_metrics(self, metrics) -> None:
        if not metrics:
            return
        logging.info(
            "[Filtering] total=%s, duplicates=%s, geo=%s, eligibility=%s, final=%s",
            metrics.total_input,
            metrics.duplicates_removed,
            metrics.geo_filtered,
            metrics.eligibility_filtered,
            metrics.final_count,
        )

    def _log_enrichment_metrics(self, vendors: List[VendorRecord]) -> None:
        total = len(vendors)
        if total == 0:
            logging.info("[Enrichment] no vendors to enrich")
            return
        email = sum(1 for v in vendors if v.email)
        phone = sum(1 for v in vendors if v.phone)
        website = sum(1 for v in vendors if v.website)
        website_content = sum(1 for v in vendors if "website_content" in v.filtering_metadata)
        logging.info(
            "[Enrichment] total=%s, email=%s, phone=%s, website=%s, website_content=%s",
            total,
            email,
            phone,
            website,
            website_content,
        )

    def _log_matching_metrics(self, matcher: CapabilityMatcher) -> None:
        if not hasattr(matcher, "get_metrics"):
            return
        metrics = matcher.get_metrics()
        if not metrics:
            return
        logging.info(
            "[Matching] total=%s, llm_attempted=%s, llm_success=%s, rule_based=%s, scraped_fallbacks=%s, metadata_fallbacks=%s",
            metrics.total_vendors,
            metrics.llm_attempted,
            metrics.llm_succeeded,
            metrics.rule_based,
            metrics.scraped_fallbacks,
            metrics.metadata_fallbacks,
        )

    def _annotate_match_status(
        self, matches: List[VendorMatchResult], threshold: float, batch_id: int
    ) -> None:
        for match in matches:
            vendor = match.vendor
            status: str
            reason: str
            if match.capability_match_score >= threshold:
                status = "selected"
                reason = f"Meets score threshold ({match.capability_match_score:.1f})"
            else:
                status = "needs_review"
                scrape_error = vendor.filtering_metadata.get("scrape_error")
                if scrape_error:
                    reason = f"Website not captured: {scrape_error}"
                elif not vendor.filtering_metadata.get("website_content"):
                    reason = "No website content available"
                elif not vendor.email and not vendor.phone:
                    reason = "Missing contact details"
                else:
                    reason = f"Score below threshold ({match.capability_match_score:.1f})"

            vendor.filtering_metadata["match_status"] = status
            vendor.filtering_metadata["match_reason"] = reason
            vendor.filtering_metadata.setdefault("batch", batch_id)

    def _select_batch_vendors(
        self,
        vendors: List[VendorRecord],
        processed_batches: List[int],
    ) -> tuple[List[VendorRecord], dict]:
        cfg = self.context.config
        batch_size = cfg.discovery.batch_size or cfg.filtering.max_candidates or len(vendors)
        batch_size = max(1, batch_size)
        batch_id = max(1, cfg.discovery.processing_batch)

        for idx, vendor in enumerate(vendors):
            vendor.filtering_metadata.setdefault("batch", (idx // batch_size) + 1)

        start = (batch_id - 1) * batch_size
        end = start + batch_size
        batch_slice = vendors[start:end]

        info = {
            "batch_id": batch_id,
            "processed_batches": processed_batches,
            "batch_size": batch_size,
        }
        return batch_slice, info

    def _write_vendor_cache(
        self, profile: TenderProfile, vendors: List[VendorRecord]
    ) -> None:
        path = self._get_cache_path(profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tender_id": self._cache_key(profile),
            "batch_size": self.context.config.discovery.batch_size
            or self.context.config.filtering.max_candidates
            or len(vendors),
            "processed_batches": [],
            "vendors": [asdict(v) for v in vendors],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load_cached_vendors(self, profile: TenderProfile):
        path = self._get_cache_path(profile)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            logging.warning("Cache file corrupted, ignoring: %s", path)
            return None

        vendor_dicts = data.get("vendors", [])
        vendors = [self._vendor_from_dict(v) for v in vendor_dicts]
        return {
            "vendors": vendors,
            "processed_batches": data.get("processed_batches", []),
            "batch_size": data.get("batch_size"),
        }

    def _update_cache_batches(
        self, profile: TenderProfile, processed_batches: List[int]
    ) -> None:
        if not processed_batches:
            return
        path = self._get_cache_path(profile)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            logging.warning("Cache file corrupted, cannot update batches: %s", path)
            return
        existing = set(data.get("processed_batches", []))
        for batch_id in processed_batches:
            if batch_id:
                existing.add(batch_id)
        data["processed_batches"] = sorted(existing)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _get_cache_path(self, profile: TenderProfile) -> Path:
        cache_dir = paths.output_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = self._cache_key(profile)
        return cache_dir / f"{key}_vendors.json"

    def _cache_key(self, profile: TenderProfile) -> str:
        if profile.tender_id:
            return profile.tender_id.replace("/", "-")
        reference = (
            profile.doc_extracted.structured.reference_number
            if profile.doc_extracted
            else None
        )
        return (reference or "manual").replace("/", "-")

    def _vendor_from_dict(self, payload: dict) -> VendorRecord:
        contact_data = payload.get("primary_contact")
        if contact_data:
            payload["primary_contact"] = ContactInfo(**contact_data)
        return VendorRecord(**payload)
