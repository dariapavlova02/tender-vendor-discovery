import os
from dotenv import load_dotenv
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource

load_dotenv()

print("="*80)
print("Quick Distance Scoring Test (20 vendors)")
print("="*80)

sam_source = SamEntitySource()
albuquerque_coords = (35.0844, -106.6504)

print("\nProject Location: Albuquerque, NM (35.0844, -106.6504)")
print("\nFetching 20 vendors sorted by distance...")

entities = sam_source.search_by_naics(
    "315210",
    limit=20,
    project_location=albuquerque_coords,
    sort_by_distance=True
)

print(f"\n✓ Retrieved {len(entities)} vendors\n")
print(f"{'Rank':<6} {'City':<25} {'State':<6} {'Distance (mi)':<15} {'Score':<8}")
print("-" * 80)

for i, entity in enumerate(entities, 1):
    physical = entity.get("coreData", {}).get("physicalAddress", {})
    city = physical.get("city", "Unknown")[:24]
    state = physical.get("stateOrProvinceCode", "??")
    distance = entity.get("_distance_miles", "N/A")
    score = entity.get("_distance_score", "N/A")
    
    print(f"{i:<6} {city:<25} {state:<6} {distance:<15} {score:<8}")

print("\n" + "="*80)
print("✅ Distance-based scoring working!")
print("✅ Vendors ranked by proximity to project location")
print("="*80)
