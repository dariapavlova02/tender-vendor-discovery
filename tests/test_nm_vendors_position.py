import os
from dotenv import load_dotenv
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource

load_dotenv()

print("="*80)
print("NM Vendors Position Analysis")
print("="*80)

sam_source = SamEntitySource()
albuquerque_coords = (35.0844, -106.6504)

print("\nProject Location: Albuquerque, NM")
print("Fetching top 200 vendors sorted by distance...\n")

entities = sam_source.search_by_naics(
    "315210",
    limit=200,
    project_location=albuquerque_coords,
    sort_by_distance=True
)

nm_vendors = [(i+1, e) for i, e in enumerate(entities) if 
              e.get("coreData", {}).get("physicalAddress", {}).get("stateOrProvinceCode") == "NM"]

print(f"Found {len(nm_vendors)} NM vendors in top 200\n")

if nm_vendors:
    print("NM Vendors Positions:")
    print(f"{'Rank':<8} {'City':<25} {'Distance (mi)':<15} {'Score':<8}")
    print("-" * 80)
    
    for rank, entity in nm_vendors[:15]:
        physical = entity.get("coreData", {}).get("physicalAddress", {})
        city = physical.get("city", "Unknown")[:24]
        distance = entity.get("_distance_miles", "N/A")
        score = entity.get("_distance_score", "N/A")
        
        print(f"{rank:<8} {city:<25} {distance:<15} {score:<8}")
else:
    print("⚠️ No NM vendors found in top 200!")

print("\n" + "="*80)
