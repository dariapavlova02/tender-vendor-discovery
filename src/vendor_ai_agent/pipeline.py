"""High-level orchestration for the Tender Vendor AI Agent."""
from __future__ import annotations

import logging
from dataclasses import dataclass
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
from .models import PipelineArtifacts, TenderProfile, TenderSection, VendorMatchResult
from .modules import (
    CapabilityMatcher,
    DocumentFetcher,
    DocumentParser,
    MetadataBackfill,
    OpenAIProvider,
    OutputGenerator,
    RequirementExtractor,
    VendorDiscovery,
    VendorEnricher,
    VendorFilter,
)


from .sources.sam_entity import SamEntitySource
from .sources import CanadaContractsVendorSource
from .database.connection import get_session
from .enrichment_providers import WebsiteContentProvider

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
        
        # Initialize LLM provider if configured
        # Use CHEAP model (gpt-4o-mini) for TenderProfiler - simple keyword extraction task
        llm_provider = None
        try:
            llm_provider = OpenAIProvider(
                default_model=cfg.llm.cheap_model,  # Use cheap model for profiling
                use_flex_tier=cfg.llm.use_flex_tier
            )
            logging.info("LLM provider initialized with model: %s", cfg.llm.cheap_model)
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
            from .modules.website_scraper import WebsiteScraper
            scraper = WebsiteScraper(
                timeout_seconds=cfg.capability_matching.scrape_timeout_seconds,
                max_content_chars=cfg.capability_matching.max_content_chars
            )
            website_provider = WebsiteContentProvider(scraper=scraper)
            enrichment_providers.append(website_provider)
            logging.info("WebsiteContentProvider registered for enrichment")
        
        if cfg.enrichment.enable_contact_scraping and cfg.serper_api_key:
            from .enrichment_providers import ContactScrapingProvider, SerperClient
            serper_client = SerperClient(api_key=cfg.serper_api_key)
            contact_provider = ContactScrapingProvider(
                llm_provider=llm_provider,
                scraper_timeout=cfg.enrichment.scraper_timeout_seconds,
                enable_llm_fallback=cfg.enrichment.enable_llm_fallback,
                serper_client=serper_client,
                enable_targeted_serper=cfg.enrichment.enable_targeted_serper_fallback
            )
            enrichment_providers.append(contact_provider)
            logging.info("ContactScrapingProvider registered with 3-level fallback")
        
        self.context = PipelineContext(
            config=cfg,
            document_parser=DocumentParser(),
            document_fetcher=DocumentFetcher(),
            requirement_extractor=RequirementExtractor(llm_provider=llm_provider),
            vendor_discovery=VendorDiscovery(sources=sources),
            vendor_enricher=VendorEnricher(
                providers=enrichment_providers,
                max_workers=cfg.enrichment.max_enrichment_workers,
                batch_size=cfg.enrichment.batch_size,
                min_batch_success_rate=cfg.enrichment.min_batch_success_rate,
                max_enrichment_batches=cfg.enrichment.max_enrichment_batches,
                target_relevant_vendors=cfg.enrichment.target_relevant_vendors,
                enable_batch_quality_gates=cfg.enrichment.enable_batch_quality_gates,
                enable_sampling_fallback=cfg.enrichment.enable_sampling_fallback,
                sample_positions=cfg.enrichment.sample_positions,
                relevance_score_threshold=cfg.enrichment.relevance_score_threshold
            ),
            vendor_filter=VendorFilter(config=cfg.filtering),
            capability_matcher=CapabilityMatcher(llm_provider=llm_provider, config=cfg.capability_matching),
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
        
        try:
            discovered_vendors = self.context.vendor_discovery.discover(tender_profile)
        except Exception as e:
            raise Exception(f"Vendor discovery failed: {e}")
        
        filtered_vendors = self.context.vendor_filter.filter(tender_profile, discovered_vendors)
        filtering_metrics = self.context.vendor_filter.get_metrics()
        
        if hasattr(self.context.vendor_enricher, 'enrich_with_scoring'):
            enriched_vendors, relevant_matches = self.context.vendor_enricher.enrich_with_scoring(
                profile=tender_profile,
                vendors=filtered_vendors,
                scoring_fn=self.context.capability_matcher.score
            )
            matches = relevant_matches if relevant_matches else self.context.capability_matcher.score(
                tender_profile, enriched_vendors
            )
        else:
            enriched_vendors = self.context.vendor_enricher.enrich(filtered_vendors)
            matches = self.context.capability_matcher.score(tender_profile, enriched_vendors)
        
        return PipelineArtifacts(
            tender_sections=sections,
            tender_profile=tender_profile,
            raw_vendors=discovered_vendors,
            enriched_vendors=enriched_vendors,
            filtered_vendors=filtered_vendors,
            filtering_metrics=filtering_metrics,
            final_matches=matches,
        )

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
