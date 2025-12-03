"""Streaming pipeline state management with queue infrastructure."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..models import VendorMatchResult, VendorRecord

logger = logging.getLogger(__name__)


@dataclass
class BatchMetrics:
    batch_num: int
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    vendors_count: int = 0
    enrichment_time: float = 0.0
    scoring_time: float = 0.0
    relevant_count: int = 0
    
    def finalize(self) -> None:
        self.end_time = time.time()
    
    @property
    def total_time(self) -> float:
        if self.end_time is None:
            return 0.0
        return self.end_time - self.start_time


@dataclass
class StreamingJobState:
    run_dir: Path
    max_queue_size: int = 5
    max_concurrent_batches: int = 2
    checkpoint_interval: int = 50
    
    vendor_queue: Optional[asyncio.Queue] = None
    result_queue: Optional[asyncio.Queue] = None
    seen_vendors: Set[str] = field(default_factory=set)
    writer_task: Optional[asyncio.Task] = None
    checkpoint_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    total_discovered: int = 0
    total_enriched: int = 0
    total_relevant: int = 0
    batch_metrics: List[BatchMetrics] = field(default_factory=list)
    
    discovery_start_time: Optional[float] = None
    discovery_end_time: Optional[float] = None
    
    _initialized: bool = False
    
    def __post_init__(self) -> None:
        self.run_dir = Path(self.run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
    
    def initialize(self) -> None:
        if self._initialized:
            return
        
        self.vendor_queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.result_queue = asyncio.Queue(maxsize=100)
        self._initialized = True
        logger.info(
            f"Streaming state initialized: queue_size={self.max_queue_size}, "
            f"concurrent_batches={self.max_concurrent_batches}"
        )
    
    def add_discovered_vendor(self, vendor: VendorRecord) -> bool:
        vendor_key = self._get_vendor_key(vendor)
        if vendor_key in self.seen_vendors:
            return False
        self.seen_vendors.add(vendor_key)
        self.total_discovered += 1
        return True
    
    def record_batch_start(self, batch_num: int, vendors_count: int) -> BatchMetrics:
        metrics = BatchMetrics(batch_num=batch_num, vendors_count=vendors_count)
        self.batch_metrics.append(metrics)
        return metrics
    
    def log_progress(self) -> None:
        logger.info(
            f"Progress: discovered={self.total_discovered}, "
            f"enriched={self.total_enriched}, "
            f"relevant={self.total_relevant}, "
            f"batches={len(self.batch_metrics)}"
        )
    
    def get_summary(self) -> Dict[str, Any]:
        discovery_time = 0.0
        if self.discovery_start_time and self.discovery_end_time:
            discovery_time = self.discovery_end_time - self.discovery_start_time
        
        total_enrichment_time = sum(m.enrichment_time for m in self.batch_metrics)
        total_scoring_time = sum(m.scoring_time for m in self.batch_metrics)
        
        return {
            "total_discovered": self.total_discovered,
            "total_enriched": self.total_enriched,
            "total_relevant": self.total_relevant,
            "batches_processed": len(self.batch_metrics),
            "discovery_time_seconds": discovery_time,
            "total_enrichment_time_seconds": total_enrichment_time,
            "total_scoring_time_seconds": total_scoring_time,
            "avg_batch_time_seconds": (
                sum(m.total_time for m in self.batch_metrics) / len(self.batch_metrics)
                if self.batch_metrics else 0.0
            ),
        }
    
    @staticmethod
    def _get_vendor_key(vendor: VendorRecord) -> str:
        if vendor.uei:
            return f"uei:{vendor.uei}"
        if vendor.duns:
            return f"duns:{vendor.duns}"
        domain = vendor.filtering_metadata.get('domain') or vendor.filtering_metadata.get('serper_domain')
        if domain:
            return f"domain:{domain.lower()}"
        return f"name:{vendor.company_name.lower()}"


class ParquetStreamWriter:
    def __init__(self, output_path: Path, schema: pa.Schema) -> None:
        self.output_path = output_path
        self.schema = schema
        self.writer: Optional[pq.ParquetWriter] = None
        self.batches_written = 0
        self.rows_written = 0
        self.logger = logging.getLogger(__name__)
    
    def open(self) -> None:
        if self.writer is not None:
            return
        self.writer = pq.ParquetWriter(self.output_path, self.schema)
        self.logger.info(f"Parquet writer opened: {self.output_path}")
    
    def write_batch(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        
        if self.writer is None:
            self.open()
        
        if self.writer is None:
            raise RuntimeError("Failed to open Parquet writer")
        
        table = pa.Table.from_pylist(records, schema=self.schema)
        self.writer.write_table(table)
        self.batches_written += 1
        self.rows_written += len(records)
        
        if self.batches_written % 5 == 0:
            self.logger.info(
                f"Parquet writer progress: {self.rows_written} rows, {self.batches_written} batches"
            )
    
    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            self.writer = None
            self.logger.info(
                f"Parquet writer closed: {self.output_path} "
                f"({self.rows_written} rows, {self.batches_written} batches)"
            )
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


async def parquet_writer_task(
    result_queue: asyncio.Queue,
    output_path: Path,
    schema: pa.Schema,
) -> int:
    logger.info(f"Parquet writer task started: {output_path}")
    rows_written = 0
    
    with ParquetStreamWriter(output_path, schema) as writer:
        while True:
            batch = await result_queue.get()
            
            if batch is None:
                logger.info("Parquet writer received shutdown signal")
                break
            
            try:
                writer.write_batch(batch)
                rows_written += len(batch)
            except Exception as e:
                logger.error(f"Error writing batch to Parquet: {e}")
                raise
            finally:
                result_queue.task_done()
    
    logger.info(f"Parquet writer task finished: {rows_written} total rows")
    return rows_written


def create_vendor_match_schema() -> pa.Schema:
    return pa.schema([
        pa.field("company_name", pa.string()),
        pa.field("website", pa.string()),
        pa.field("email", pa.string()),
        pa.field("phone", pa.string()),
        pa.field("location", pa.string()),
        pa.field("city", pa.string()),
        pa.field("state", pa.string()),
        pa.field("country", pa.string()),
        pa.field("industry", pa.string()),
        pa.field("source", pa.string()),
        pa.field("is_past_winner", pa.bool_()),
        pa.field("enrichment_flags", pa.string()),
        pa.field("uei", pa.string()),
        pa.field("duns", pa.string()),
        pa.field("cage_code", pa.string()),
        pa.field("business_types", pa.string()),
        pa.field("primary_contact_name", pa.string()),
        pa.field("primary_contact_email", pa.string()),
        pa.field("primary_contact_phone", pa.string()),
        pa.field("geo_score", pa.float64()),
        pa.field("preliminary_score", pa.float64()),
        pa.field("filtering_metadata", pa.string()),
        pa.field("total_contract_value", pa.float64()),
        pa.field("contract_count", pa.int64()),
        pa.field("capability_match_score", pa.float64()),
        pa.field("rationale", pa.string()),
        pa.field("references", pa.string()),
    ])


def create_vendor_schema() -> pa.Schema:
    return pa.schema([
        pa.field("company_name", pa.string()),
        pa.field("website", pa.string()),
        pa.field("email", pa.string()),
        pa.field("phone", pa.string()),
        pa.field("location", pa.string()),
        pa.field("city", pa.string()),
        pa.field("state", pa.string()),
        pa.field("country", pa.string()),
        pa.field("industry", pa.string()),
        pa.field("source", pa.string()),
        pa.field("is_past_winner", pa.bool_()),
        pa.field("enrichment_flags", pa.string()),
        pa.field("uei", pa.string()),
        pa.field("duns", pa.string()),
        pa.field("cage_code", pa.string()),
        pa.field("business_types", pa.string()),
        pa.field("primary_contact_name", pa.string()),
        pa.field("primary_contact_email", pa.string()),
        pa.field("primary_contact_phone", pa.string()),
        pa.field("geo_score", pa.float64()),
        pa.field("preliminary_score", pa.float64()),
        pa.field("filtering_metadata", pa.string()),
        pa.field("total_contract_value", pa.float64()),
        pa.field("contract_count", pa.int64()),
    ])
