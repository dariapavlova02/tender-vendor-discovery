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
    OutputGenerator,
    RequirementExtractor,
    VendorDiscovery,
    VendorEnricher,
    VendorFilter,
)


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
        self.context = PipelineContext(
            config=cfg,
            document_parser=DocumentParser(),
            document_fetcher=DocumentFetcher(),
            requirement_extractor=RequirementExtractor(),
            vendor_discovery=VendorDiscovery(),
            vendor_enricher=VendorEnricher(),
            vendor_filter=VendorFilter(),
            capability_matcher=CapabilityMatcher(),
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
        discovered_vendors = self.context.vendor_discovery.discover(tender_profile)
        enriched_vendors = self.context.vendor_enricher.enrich(discovered_vendors)
        filtered_vendors = self.context.vendor_filter.filter(tender_profile, enriched_vendors)
        matches = self.context.capability_matcher.score(tender_profile, filtered_vendors)
        return PipelineArtifacts(
            tender_sections=sections,
            tender_profile=tender_profile,
            raw_vendors=discovered_vendors,
            enriched_vendors=enriched_vendors,
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
