#!/usr/bin/env python3
"""
Debug script to test Canada CSV processing performance
"""
import time
import pandas as pd
from pathlib import Path

csv_path = Path("data/canada_history/2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv")

print(f"Testing CSV read performance: {csv_path}")
print(f"File size: {csv_path.stat().st_size / 1024 / 1024:.1f} MB")
print()

# Test 1: Read first chunk
print("Test 1: Reading first 10,000 rows...")
start = time.time()
chunk_iter = pd.read_csv(
    csv_path,
    chunksize=10000,
    low_memory=False,
    encoding="utf-8-sig",
    on_bad_lines="skip",
    encoding_errors="ignore"
)
first_chunk = next(chunk_iter)
elapsed = time.time() - start
print(f"  ✓ First chunk read in {elapsed:.2f}s")
print(f"  Columns: {len(first_chunk.columns)}")
print(f"  Rows: {len(first_chunk)}")
print()

# Test 2: Process vendor aggregation
print("Test 2: Aggregating vendors from first chunk...")
start = time.time()

aggregates = {}
for _, row in first_chunk.iterrows():
    legal_name = row.get("supplierLegalName-nomLegalFournisseur-eng")
    standardized_name = row.get("supplierStandardizedName-nomNormaliseFournisseur-eng")
    postal_code = row.get("supplierAddressPostalCode-fournisseurAdresseCodePostal")
    
    if pd.isna(standardized_name) and pd.isna(legal_name):
        continue
    
    vendor_name = standardized_name if not pd.isna(standardized_name) else legal_name
    vendor_key = f"{vendor_name}|{postal_code if not pd.isna(postal_code) else 'NO_POSTAL'}"
    
    if vendor_key not in aggregates:
        aggregates[vendor_key] = {"count": 0}
    
    aggregates[vendor_key]["count"] += 1

elapsed = time.time() - start
print(f"  ✓ Aggregated in {elapsed:.2f}s")
print(f"  Unique vendors: {len(aggregates)}")
print()

# Test 3: Read multiple chunks
print("Test 3: Reading first 5 chunks (50,000 rows)...")
start = time.time()
chunk_iter = pd.read_csv(
    csv_path,
    chunksize=10000,
    low_memory=False,
    encoding="utf-8-sig",
    on_bad_lines="skip",
    encoding_errors="ignore"
)

chunks_read = 0
rows_total = 0
for chunk in chunk_iter:
    chunks_read += 1
    rows_total += len(chunk)
    if chunks_read >= 5:
        break

elapsed = time.time() - start
print(f"  ✓ Read {chunks_read} chunks ({rows_total} rows) in {elapsed:.2f}s")
print(f"  Average: {elapsed / chunks_read:.2f}s per chunk")
print()

print("Performance summary:")
print(f"  Estimated time for 5M rows: {(elapsed / chunks_read) * (5000000 / 10000) / 60:.1f} minutes")
print()
print("Column names (first 10):")
for i, col in enumerate(list(first_chunk.columns)[:10]):
    print(f"  {i+1}. {col}")
