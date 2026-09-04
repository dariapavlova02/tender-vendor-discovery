"""Streaming pipeline implementation with producer-consumer pattern."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from ..models import TenderProfile, VendorMatchResult, VendorRecord
from .streaming_state import (
    BatchMetrics,
    StreamingJobState,
    create_vendor_match_schema,
    parquet_writer_task,
)

logger = logging.getLogger(__name__)


async def discovery_producer(
    profile: TenderProfile,
    vendors: List[VendorRecord],
    state: StreamingJobState,
    batch_size: int = 50,
) -> None:
    logger.info(
        f"Discovery producer started: {len(vendors)} vendors, batch_size={batch_size}"
    )
    state.discovery_start_time = time.time()
    
    vendor_queue = state.vendor_queue
    if vendor_queue is None:
        raise RuntimeError("State not initialized")
    
    deduplicated_vendors: List[VendorRecord] = []
    duplicates_removed = 0
    
    for vendor in vendors:
        if state.add_discovered_vendor(vendor):
            deduplicated_vendors.append(vendor)
        else:
            duplicates_removed += 1
    
    if duplicates_removed > 0:
        logger.info(
            f"Removed {duplicates_removed} duplicate vendors during Discovery"
        )
    
    batches_sent = 0
    for i in range(0, len(deduplicated_vendors), batch_size):
        batch = deduplicated_vendors[i:i+batch_size]
        
        await vendor_queue.put(batch)
        batches_sent += 1
        
        if batches_sent % 5 == 0:
            logger.info(
                f"Discovery progress: {batches_sent} batches sent "
                f"({i+len(batch)}/{len(deduplicated_vendors)} vendors), "
                f"queue_size={vendor_queue.qsize()}"
            )
    
    for _ in range(state.max_concurrent_batches):
        await vendor_queue.put(None)
    
    state.discovery_end_time = time.time()
    discovery_time = state.discovery_end_time - state.discovery_start_time
    logger.info(
        f"Discovery producer finished: {len(deduplicated_vendors)} vendors "
        f"in {batches_sent} batches ({discovery_time:.1f}s)"
    )


async def enrichment_consumer(
    consumer_id: int,
    profile: TenderProfile,
    state: StreamingJobState,
    enricher_enrich_async: Callable,
    scorer_score_async: Callable,
    relevance_threshold: float = 70.0,
) -> None:
    logger.info(f"Enrichment consumer {consumer_id} started")
    
    vendor_queue = state.vendor_queue
    result_queue = state.result_queue
    if vendor_queue is None or result_queue is None:
        raise RuntimeError("State not initialized")
    
    batches_processed = 0
    
    while True:
        batch = await vendor_queue.get()
        
        if batch is None:
            vendor_queue.task_done()
            logger.info(
                f"Consumer {consumer_id} received shutdown signal, "
                f"processed {batches_processed} batches"
            )
            break
        
        try:
            batch_num = len(state.batch_metrics) + 1
            metrics = state.record_batch_start(batch_num, len(batch))
            
            logger.debug(
                f"Consumer {consumer_id} processing batch {batch_num} "
                f"({len(batch)} vendors)"
            )
            
            enrich_start = time.time()
            enriched_batch = await enricher_enrich_async(batch)
            metrics.enrichment_time = time.time() - enrich_start
            
            content_ready = [
                v for v in enriched_batch
                if v.filtering_metadata.get("website_content")
            ]
            
            if not content_ready:
                logger.warning(
                    f"Consumer {consumer_id} batch {batch_num}: "
                    f"no vendors with website content, skipping scoring"
                )
                scored_batch = []
            else:
                scoring_start = time.time()
                scored_batch = await scorer_score_async(profile, content_ready)
                metrics.scoring_time = time.time() - scoring_start
            
            relevant_matches = [
                r for r in scored_batch
                if r.capability_match_score >= relevance_threshold
                and r.vendor.filtering_metadata.get("scoring_method") != "rule_based"
            ]
            
            metrics.relevant_count = len(relevant_matches)
            metrics.finalize()
            
            state.total_enriched += len(enriched_batch)
            state.total_relevant += len(relevant_matches)
            
            if scored_batch:
                result_records = [_match_to_dict(m) for m in scored_batch]
                await result_queue.put(result_records)
            
            batches_processed += 1
            
            logger.info(
                f"Consumer {consumer_id} batch {batch_num} complete: "
                f"{len(relevant_matches)}/{len(batch)} relevant "
                f"({len(relevant_matches)/len(batch)*100:.1f}%), "
                f"enrich={metrics.enrichment_time:.1f}s, "
                f"score={metrics.scoring_time:.1f}s"
            )
            
            if batches_processed % 3 == 0:
                state.log_progress()
        
        except Exception as e:
            logger.error(
                f"Consumer {consumer_id} error processing batch: {e}",
                exc_info=True
            )
        finally:
            vendor_queue.task_done()
    
    logger.info(
        f"Enrichment consumer {consumer_id} finished: {batches_processed} batches"
    )


async def run_streaming_pipeline(
    profile: TenderProfile,
    vendors: List[VendorRecord],
    state: StreamingJobState,
    enricher_enrich_async: Callable,
    scorer_score_async: Callable,
    batch_size: int = 50,
    relevance_threshold: float = 70.0,
) -> Dict[str, Any]:
    logger.info(
        f"Starting streaming pipeline: {len(vendors)} vendors, "
        f"batch_size={batch_size}, max_concurrent_batches={state.max_concurrent_batches}"
    )
    
    state.initialize()
    
    result_queue = state.result_queue
    if result_queue is None:
        raise RuntimeError("State not initialized")
    
    output_path = state.run_dir / "all_matches.parquet"
    schema = create_vendor_match_schema()
    
    writer_task = asyncio.create_task(
        parquet_writer_task(result_queue, output_path, schema)
    )
    state.writer_task = writer_task
    
    consumer_tasks = [
        asyncio.create_task(
            enrichment_consumer(
                consumer_id=i,
                profile=profile,
                state=state,
                enricher_enrich_async=enricher_enrich_async,
                scorer_score_async=scorer_score_async,
                relevance_threshold=relevance_threshold,
            )
        )
        for i in range(state.max_concurrent_batches)
    ]
    
    producer_task = asyncio.create_task(
        discovery_producer(profile, vendors, state, batch_size)
    )
    
    await producer_task
    
    await asyncio.gather(*consumer_tasks)
    
    await result_queue.put(None)
    
    rows_written = await writer_task
    
    summary = state.get_summary()
    summary["rows_written"] = rows_written
    
    logger.info(
        f"Streaming pipeline complete: "
        f"discovered={summary['total_discovered']}, "
        f"enriched={summary['total_enriched']}, "
        f"relevant={summary['total_relevant']}, "
        f"discovery_time={summary['discovery_time_seconds']:.1f}s, "
        f"avg_batch_time={summary['avg_batch_time_seconds']:.1f}s"
    )
    
    return summary


def _match_to_dict(match: VendorMatchResult) -> Dict[str, Any]:
    vendor = match.vendor
    primary_contact = vendor.primary_contact
    
    return {
        "company_name": vendor.company_name,
        "website": vendor.website,
        "email": vendor.email,
        "phone": vendor.phone,
        "location": vendor.location,
        "city": vendor.city,
        "state": vendor.state,
        "country": vendor.country,
        "industry": vendor.industry,
        "source": vendor.source,
        "is_past_winner": vendor.is_past_winner,
        "enrichment_flags": json.dumps(vendor.enrichment_flags or []),
        "uei": vendor.uei,
        "duns": vendor.duns,
        "cage_code": vendor.cage_code,
        "business_types": json.dumps(vendor.business_types or []),
        "primary_contact_name": primary_contact.name if primary_contact else None,
        "primary_contact_email": primary_contact.email if primary_contact else None,
        "primary_contact_phone": primary_contact.phone if primary_contact else None,
        "geo_score": vendor.geo_score,
        "preliminary_score": vendor.preliminary_score,
        "filtering_metadata": json.dumps(vendor.filtering_metadata or {}),
        "total_contract_value": vendor.total_contract_value,
        "contract_count": vendor.contract_count,
        "capability_match_score": match.capability_match_score,
        "rationale": match.rationale,
        "references": json.dumps(match.references or []),
    }
