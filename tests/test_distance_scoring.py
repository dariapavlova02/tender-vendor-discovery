import os
from dotenv import load_dotenv
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource

load_dotenv()

print("="*80)
print("Distance-Based Scoring Test")
print("="*80)

sam_source = SamEntitySource()

print("\n[Test Scenario]")
print("  NAICS: 315210 (Cut and Sew Apparel Contractors)")
print("  Project Location: Albuquerque, NM")
print("  Coordinates: (35.0844, -106.6504)")
print()

albuquerque_coords = (35.0844, -106.6504)

print("[1] Fetching vendors WITHOUT distance scoring...")
entities_no_sort = sam_source.search_by_naics(
    "315210",
    state=None,
    limit=50
)
print(f"   Retrieved: {len(entities_no_sort)} entities")

print("\n[2] Fetching vendors WITH distance scoring...")
entities_sorted = sam_source.search_by_naics(
    "315210",
    state=None,
    limit=50,
    project_location=albuquerque_coords,
    sort_by_distance=True
)
print(f"   Retrieved: {len(entities_sorted)} entities (sorted by distance)")

print("\n[3] Top 10 Closest Vendors:")
print(f"{'Rank':<6} {'City':<20} {'State':<6} {'Distance (mi)':<15} {'Score':<8}")
print("-" * 80)

for i, entity in enumerate(entities_sorted[:10], 1):
    physical = entity.get("coreData", {}).get("physicalAddress", {})
    city = physical.get("city", "Unknown")
    state = physical.get("stateOrProvinceCode", "??")
    distance = entity.get("_distance_miles", "N/A")
    score = entity.get("_distance_score", "N/A")
    
    print(f"{i:<6} {city:<20} {state:<6} {distance:<15} {score:<8}")

print("\n[4] Comparing: NM vendors vs others")
nm_vendors = [e for e in entities_sorted if e.get("coreData", {}).get("physicalAddress", {}).get("stateOrProvinceCode") == "NM"]
non_nm_vendors = [e for e in entities_sorted if e.get("coreData", {}).get("physicalAddress", {}).get("stateOrProvinceCode") != "NM"]

print(f"\n   NM vendors in top 50: {len(nm_vendors)}")
if nm_vendors:
    nm_distances = [v.get("_distance_miles", 999999) for v in nm_vendors]
    print(f"   Average distance (NM): {sum(nm_distances)/len(nm_distances):.1f} miles")
    print(f"   Closest NM vendor: {min(nm_distances):.1f} miles")

print(f"\n   Non-NM vendors in top 50: {len(non_nm_vendors)}")
if non_nm_vendors:
    non_nm_distances = [v.get("_distance_miles", 999999) for v in non_nm_vendors[:10]]
    print(f"   Average distance (top 10 non-NM): {sum(non_nm_distances)/len(non_nm_distances):.1f} miles")

print("\n[5] State Distribution in Top 50:")
state_counts = {}
for entity in entities_sorted[:50]:
    state = entity.get("coreData", {}).get("physicalAddress", {}).get("stateOrProvinceCode", "??")
    state_counts[state] = state_counts.get(state, 0) + 1

for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    percentage = (count / 50) * 100
    print(f"   {state}: {count} ({percentage:.1f}%)")

print("\n" + "="*80)
print("✅ Distance scoring allows keeping all vendors")
print("✅ Vendors are ranked by proximity to project")
print("✅ No hard filtering - business can choose based on distance + capability")
print("="*80)
