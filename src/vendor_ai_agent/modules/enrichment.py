"""Vendor data enrichment via websites and APIs."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

from ..contracts import EnrichmentProvider, VendorEnricherContract
from ..models import TenderProfile, VendorMatchResult, VendorRecord


@dataclass
class BatchEnrichmentResult:
    """Result of enriching and scoring a batch of vendors."""
    enriched_vendors: List[VendorRecord]
    scored_results: List[VendorMatchResult]
    relevant_count: int
    success_rate: float
    batch_number: int
    total_enriched: int


class VendorEnricher(VendorEnricherContract):
    """Adds contact and metadata fields to vendor records."""

    def __init__(
        self, 
        providers: Sequence[EnrichmentProvider] | None = None,
        max_workers: int = 10,
        batch_size: int = 50,
        min_batch_success_rate: float = 0.15,
        max_enrichment_batches: int = 5,
        target_relevant_vendors: int = 200,
        enable_batch_quality_gates: bool = True,
        enable_sampling_fallback: bool = True,
        sample_positions: Optional[List[int]] = None,
        relevance_score_threshold: float = 70.0
    ) -> None:
        if providers is None:
            from ..enrichment_providers import StaticContactsProvider
            providers = [StaticContactsProvider()]
        self.providers: List[EnrichmentProvider] = list(providers)
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.min_batch_success_rate = min_batch_success_rate
        self.max_enrichment_batches = max_enrichment_batches
        self.target_relevant_vendors = target_relevant_vendors
        self.enable_batch_quality_gates = enable_batch_quality_gates
        self.enable_sampling_fallback = enable_sampling_fallback
        self.sample_positions = sample_positions or [150, 300]
        self.relevance_score_threshold = relevance_score_threshold
        self.logger = logging.getLogger(__name__)

    def enrich(self, vendors: Iterable[VendorRecord]) -> List[VendorRecord]:
        """Legacy method for backward compatibility - enriches all vendors."""
        vendor_list = list(vendors)
        
        if not vendor_list:
            return []
        
        if len(vendor_list) == 1 or self.max_workers == 1:
            return self._enrich_sequential(vendor_list)
        
        return self._enrich_all_parallel(vendor_list)
    
    def enrich_with_scoring(
        self,
        profile: TenderProfile,
        vendors: List[VendorRecord],
        scoring_fn: Callable[[TenderProfile, List[VendorRecord]], List[VendorMatchResult]]
    ) -> tuple[List[VendorRecord], List[VendorMatchResult], List[VendorMatchResult]]:
        """
        Enrich vendors in batches with LLM scoring and quality gates.
        
        Returns:
            Tuple of (all_enriched_vendors, all_relevant_matches)
        """
        if not vendors:
            return [], []
        
        if not self.enable_batch_quality_gates:
            self.logger.info("Batch quality gates disabled - enriching all vendors")
            enriched = self._enrich_all_parallel(vendors)
            scored = scoring_fn(profile, enriched)
            return enriched, scored, scored
        
        self.logger.info(
            f"Starting batch enrichment: {len(vendors)} candidates, "
            f"targeting {self.target_relevant_vendors} relevant vendors"
        )
        
        all_enriched: List[VendorRecord] = []
        all_scored_results: List[VendorMatchResult] = []
        all_relevant_results: List[VendorMatchResult] = []
        total_enriched = 0
        current_position = 0
        
        batch_num = 0
        while True:
            batch_num += 1
            
            if len(all_relevant_results) >= self.target_relevant_vendors:
                self.logger.info(
                    f"✓ Target reached: {len(all_relevant_results)} relevant vendors found"
                )
                break
            
            if current_position >= len(vendors):
                self.logger.info(f"No more vendors to process (exhausted {len(vendors)} candidates)")
                break
            
            batch_end = min(current_position + self.batch_size, len(vendors))
            batch = vendors[current_position:batch_end]
            
            self.logger.info(
                f"Batch {batch_num}: "
                f"enriching vendors {current_position+1}-{batch_end} ({len(batch)} vendors)"
            )
            
            batch_result = self._process_batch(profile, batch, scoring_fn, batch_num, total_enriched)
            
            all_enriched.extend(batch_result.enriched_vendors)
            all_scored_results.extend(batch_result.scored_results)
            all_relevant_results.extend([
                r for r in batch_result.scored_results
                if r.capability_match_score >= self.relevance_score_threshold
            ])
            total_enriched += len(batch_result.enriched_vendors)
            
            self.logger.info(
                f"Batch {batch_num} complete: {batch_result.relevant_count}/{len(batch)} relevant "
                f"(success rate: {batch_result.success_rate:.1%}), "
                f"total relevant so far: {len(all_relevant_results)}"
            )
            
            if self.enable_batch_quality_gates and batch_result.success_rate < self.min_batch_success_rate:
                self.logger.warning(
                    f"Low success rate in batch {batch_num}: {batch_result.success_rate:.1%}, "
                    f"but continuing because target not reached ({len(all_relevant_results)}/{self.target_relevant_vendors})"
                )
            
            current_position = batch_end
        
        self.logger.info(
            f"Batch enrichment complete: enriched {total_enriched} vendors, "
            f"found {len(all_relevant_results)} relevant (score >= {self.relevance_score_threshold})"
        )
        
        return all_enriched, all_relevant_results, all_scored_results
    
    def _process_batch(
        self,
        profile: TenderProfile,
        batch: List[VendorRecord],
        scoring_fn: Callable[[TenderProfile, List[VendorRecord]], List[VendorMatchResult]],
        batch_num: int,
        total_enriched_so_far: int
    ) -> BatchEnrichmentResult:
        """Enrich a single batch and score it."""
        enriched_batch = self._enrich_all_parallel(batch)

        content_ready, skipped_for_content = self._split_content_ready(enriched_batch)

        if skipped_for_content:
            self.logger.info(
                "Skipping %s vendors with no website content before scoring",
                len(skipped_for_content),
            )

        if not content_ready:
            self.logger.warning(
                "Batch %s has no vendors with website content; skipping scoring",
                batch_num,
            )
            scored_batch = []
        else:
            scored_batch = scoring_fn(profile, content_ready)
        
        relevant = [
            r for r in scored_batch 
            if r.capability_match_score >= self.relevance_score_threshold
        ]
        
        success_base = len(content_ready)
        success_rate = len(relevant) / success_base if success_base else 0.0
        
        return BatchEnrichmentResult(
            enriched_vendors=enriched_batch,
            scored_results=scored_batch,
            relevant_count=len(relevant),
            success_rate=success_rate,
            batch_number=batch_num,
            total_enriched=total_enriched_so_far + len(enriched_batch)
        )
    
    def _check_quality_gate(
        self,
        batch_result: BatchEnrichmentResult,
        current_position: int,
        batch_num: int,
        all_vendors: List[VendorRecord]
    ) -> tuple[bool, Optional[int]]:
        """
        Check if enrichment should continue based on success rate.
        
        Returns:
            Tuple of (should_continue, new_position)
            new_position is None if continuing sequentially
        """
        if batch_result.success_rate >= self.min_batch_success_rate:
            return True, None
        
        self.logger.warning(
            f"Low success rate in batch {batch_num}: {batch_result.success_rate:.1%} "
            f"(threshold: {self.min_batch_success_rate:.1%})"
        )
        
        if batch_num == 1 and self.enable_sampling_fallback:
            self.logger.info("First batch low quality - checking sample at deeper positions")
            
            for sample_pos in self.sample_positions:
                if sample_pos >= len(all_vendors):
                    continue
                
                sample_end = min(sample_pos + 20, len(all_vendors))
                sample = all_vendors[sample_pos:sample_end]
                
                self.logger.info(f"Sampling positions {sample_pos+1}-{sample_end} ({len(sample)} vendors)")
                
                sample_enriched = self._enrich_all_parallel(sample)
                
                sample_relevant = sum(
                    1 for v in sample_enriched 
                    if "website_content" in v.filtering_metadata
                )
                sample_rate = sample_relevant / len(sample_enriched) if sample_enriched else 0.0
                
                self.logger.info(
                    f"Sample at position {sample_pos}: {sample_relevant}/{len(sample)} "
                    f"with content ({sample_rate:.1%})"
                )
                
                if sample_rate > self.min_batch_success_rate:
                    self.logger.info(f"Found better candidates at position {sample_pos}, skipping ahead")
                    return True, max(current_position + self.batch_size, sample_pos)
            
            self.logger.warning("Sample positions also low quality - stopping enrichment")
            return False, None
        
        self.logger.warning(f"Quality gate failed at batch {batch_num} - stopping enrichment")
        return False, None
    
    def _enrich_sequential(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        enriched: List[VendorRecord] = []
        for vendor in vendors:
            for provider in self.providers:
                vendor = provider.enrich(vendor)
            enriched.append(vendor)
        return enriched
    
    def _enrich_all_parallel(self, vendors: List[VendorRecord]) -> List[VendorRecord]:
        if not vendors:
            return []
        
        self.logger.debug(f"Enriching {len(vendors)} vendors with {self.max_workers} parallel workers")
        
        def enrich_vendor(vendor: VendorRecord) -> VendorRecord:
            try:
                for provider in self.providers:
                    vendor = provider.enrich(vendor)
                return vendor
            except Exception as e:
                self.logger.error(f"Error enriching {vendor.company_name}: {e}")
                return vendor
        
        enriched_dict = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(enrich_vendor, vendor): i 
                for i, vendor in enumerate(vendors)
            }
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    enriched_dict[index] = future.result()
                except Exception as e:
                    self.logger.error(f"Future failed for vendor at index {index}: {e}")
                    enriched_dict[index] = vendors[index]
        
        return [enriched_dict[i] for i in range(len(vendors))]

    def _split_content_ready(
        self, vendors: List[VendorRecord]
    ) -> tuple[List[VendorRecord], List[VendorRecord]]:
        ready: List[VendorRecord] = []
        missing: List[VendorRecord] = []

        for vendor in vendors:
            if vendor.filtering_metadata.get("website_content"):
                ready.append(vendor)
                continue

            if not vendor.website:
                reason = "No website URL"
            elif vendor.filtering_metadata.get("scrape_error"):
                reason = f"Website not captured: {vendor.filtering_metadata['scrape_error']}"
            else:
                reason = "No website content available"

            vendor.filtering_metadata.setdefault("match_status", "needs_data")
            vendor.filtering_metadata.setdefault("match_reason", reason)
            vendor.filtering_metadata["skipped_for_scoring"] = True
            missing.append(vendor)

        return ready, missing

    def register_provider(self, provider: EnrichmentProvider) -> None:
        self.providers.append(provider)
