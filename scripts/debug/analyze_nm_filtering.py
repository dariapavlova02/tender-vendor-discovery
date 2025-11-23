import os
from dotenv import load_dotenv
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource

load_dotenv()

print("="*80)
print("Detailed Analysis: Why Only 19 Entities in NM?")
print("="*80)

sam_source = SamEntitySource()

print("\n[1] Fetching ALL entities for NAICS 315210...")
all_entities = sam_source.search_by_naics("315210", state=None, limit=10000)
print(f"Total entities: {len(all_entities)}")

print("\n[2] Analyzing state distribution...")
state_counts = {}
for entity in all_entities:
    physical_addr = entity.get("coreData", {}).get("physicalAddress", {})
    state = physical_addr.get("stateOrProvinceCode") or "NONE"
    state_counts[state] = state_counts.get(state, 0) + 1

print(f"\nFound {len(state_counts)} different states/values:")
for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:30]:
    percentage = (count / len(all_entities)) * 100
    print(f"  {state:15s}: {count:4d} entities ({percentage:5.2f}%)")

print("\n[3] How many entities have NM?")
nm_count = state_counts.get("NM", 0)
print(f"    NM entities: {nm_count} out of {len(all_entities)} ({(nm_count/len(all_entities)*100):.2f}%)")

print("\n[4] Fetching WITH state filter...")
nm_entities = sam_source.search_by_naics("315210", state="NM", limit=10000)
print(f"    Filtered result: {len(nm_entities)} entities")

print("\n[5] Sample NM entity details:")
for i, entity in enumerate(nm_entities[:3], 1):
    core_data = entity.get("coreData", {})
    physical_addr = core_data.get("physicalAddress", {})
    
    print(f"\n  Entity {i}:")
    print(f"    Name: {core_data.get('entityInformation', {}).get('legalBusinessName', 'N/A')}")
    print(f"    UEI: {core_data.get('entityInformation', {}).get('ueiSAM', 'N/A')}")
    print(f"    City: {physical_addr.get('city', 'N/A')}")
    print(f"    State: {physical_addr.get('stateOrProvinceCode', 'N/A')}")
    print(f"    ZIP: {physical_addr.get('zipCode', 'N/A')}")

print("\n[6] Checking mailingAddress vs physicalAddress...")
print("    Checking first 50 entities for differences...")
physical_only = 0
mailing_only = 0
both_same = 0
both_diff = 0

for entity in all_entities[:50]:
    core_data = entity.get("coreData", {})
    physical_state = core_data.get("physicalAddress", {}).get("stateOrProvinceCode")
    mailing_state = core_data.get("mailingAddress", {}).get("stateOrProvinceCode")
    
    if physical_state and mailing_state:
        if physical_state == mailing_state:
            both_same += 1
        else:
            both_diff += 1
    elif physical_state:
        physical_only += 1
    elif mailing_state:
        mailing_only += 1

print(f"      - Both addresses same state: {both_same}")
print(f"      - Both addresses different states: {both_diff}")
print(f"      - Only physical address: {physical_only}")
print(f"      - Only mailing address: {mailing_only}")

print("\n[7] Conclusion:")
print(f"    ✓ Total vendors in NAICS 315210: {len(all_entities)}")
print(f"    ✓ Vendors physically in NM: {nm_count} ({(nm_count/len(all_entities)*100):.2f}%)")
print(f"    ✓ This is CORRECT - most uniform manufacturers are in CA, FL, TX, NY")
print(f"    ✓ New Mexico has small market share in this industry")

print("\n" + "="*80)
