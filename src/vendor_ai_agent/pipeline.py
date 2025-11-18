"""High-level orchestration for the Tender Vendor AI Agent."""
from __future__ import annotations

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
from .models import PipelineArtifacts, TenderProfile, VendorMatchResult
from .modules import (
    CapabilityMatcher,
    DocumentFetcher,
    DocumentParser,
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
        )

    def run(
        self,
        tender_files: Iterable[Path],
        *,
        ingestion_request: Optional[TenderIngestionRequest] = None,
    ) -> PipelineArtifacts:
        base_profile: Optional[TenderProfile] = None
        if ingestion_request is not None:
            ingestion_result = self.context.ingestion_router.ingest(ingestion_request)
            tender_id = (
                ingestion_request.reference_number
                or ingestion_request.solicitation_number
            )
            base_profile = TenderProfile(
                tender_id=tender_id,
                country=ingestion_request.country,
                source_system=ingestion_request.source_system,
                api_metadata=ingestion_result.api_metadata,
            )

        file_list = [Path(path) for path in tender_files]
        if ingestion_request is not None and base_profile:
            fetched = self.context.document_fetcher.fetch(ingestion_result.attachments)
            file_list.extend(fetched)
        sections = self.context.document_parser.parse(file_list)
        tender_profile = self.context.requirement_extractor.extract(
            sections, base_profile=base_profile
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
