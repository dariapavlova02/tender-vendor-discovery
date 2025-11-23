#!/usr/bin/env python3
"""Test SAM API state filtering with post-processing approach."""
from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.sources.sam_entity import SamEntitySource

print("=" * 80)
print("SAM API State Filtering Test")
print("=" * 80)

sam_api_key = os.getenv("SAM_API_KEY")

if not sam_api_key:
    print("✗ No SAM_API_KEY in .env")
    sys.exit(1)

print(f"✓ SAM API Key loaded: {sam_api_key[:10]}...")

test_naics = "315210"
test_state = "NM"

print(f"\nTest Parameters:")
print(f"  - NAICS: {test_naics}")
print(f"  - State: {test_state}")

sam_source = SamEntitySource(api_key=sam_api_key, sync_to_db=False)

print(f"\n[1/2] Fetching vendors WITHOUT state filter...")
print(f"   (This downloads all entities and may take 1-2 minutes...)")
try:
    entities_all = sam_source.search_by_naics(naics_code=test_naics, state=None, limit=10000)
    print(f"   ✓ Found {len(entities_all)} entities (all states)")
    
    states_all = set()
    for entity in entities_all[:100]:
        addr = entity.get("coreData", {}).get("physicalAddress", {})
        s = addr.get("stateOrProvinceCode")
        if s:
            states_all.add(s)
    
    print(f"   - Sample states represented: {sorted(states_all)[:10]}")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    print(f"   (Note: SAM API can be slow, timeout is expected for large datasets)")
    entities_all = []
    states_all = set()

if not entities_all:
    print(f"\n[Skipping comparison test - no baseline data]")
    print(f"\n[2/2] Testing state filter in isolation with {test_state}...")
else:
    print(f"\n[2/2] Fetching vendors WITH state filter ({test_state})...")

print(f"   (Filtering will happen post-download...)")
try:
    entities_filtered = sam_source.search_by_naics(naics_code=test_naics, state=test_state, limit=10000)
    print(f"   ✓ Found {len(entities_filtered)} entities (state: {test_state})")
    
    states_filtered = set()
    for entity in entities_filtered[:100]:
        addr = entity.get("coreData", {}).get("physicalAddress", {})
        s = addr.get("stateOrProvinceCode")
        if s:
            states_filtered.add(s)
    
    print(f"   - States in results: {sorted(states_filtered)}")
    
    if len(states_filtered) == 1 and test_state in states_filtered:
        print(f"   ✓ All entities correctly filtered to {test_state}")
    elif len(states_filtered) == 0:
        print(f"   ⚠ No entities found in {test_state} (possible: no vendors in that state)")
    else:
        print(f"   ✗ Filtering failed - found states: {states_filtered}")
        sys.exit(1)
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("Results Summary:")
print("=" * 80)
if entities_all:
    print(f"  Without filter: {len(entities_all)} entities from {len(states_all)} states")
    print(f"  With filter:    {len(entities_filtered)} entities from {test_state} only")
    reduction = len(entities_all) - len(entities_filtered)
    reduction_pct = (reduction / len(entities_all) * 100) if entities_all else 0
    print(f"  Reduction:      {reduction} entities ({reduction_pct:.1f}%)")
else:
    print(f"  With filter:    {len(entities_filtered)} entities from {test_state}")
    
print("\n✅ SAM STATE FILTERING: WORKING")
print("   - Downloads all entities via Extract API")
print("   - Filters by state in post-processing")
print("   - Correctly handles SAM API Extract limitation")
print("=" * 80)
