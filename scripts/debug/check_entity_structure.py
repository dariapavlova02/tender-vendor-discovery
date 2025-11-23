import os
import json
from dotenv import load_dotenv
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource

load_dotenv()

print("="*80)
print("Complete Entity Structure Analysis")
print("="*80)

sam_source = SamEntitySource()

print("\nFetching 1 entity to analyze structure...")
entities = sam_source.search_by_naics("315210", state=None, limit=1)

if entities:
    entity = entities[0]
    
    print("\n[1] Top-level keys:")
    for key in entity.keys():
        print(f"    - {key}")
    
    print("\n[2] coreData structure:")
    core_data = entity.get("coreData", {})
    for key in core_data.keys():
        print(f"    - {key}")
    
    print("\n[3] entityInformation details:")
    entity_info = core_data.get("entityInformation", {})
    print(f"    Keys: {list(entity_info.keys())}")
    print(f"    legalBusinessName: {entity_info.get('legalBusinessName')}")
    print(f"    ueiSAM: {entity_info.get('ueiSAM')}")
    print(f"    entityURL: {entity_info.get('entityURL')}")
    
    print("\n[4] physicalAddress full:")
    physical = core_data.get("physicalAddress", {})
    print(json.dumps(physical, indent=2))
    
    print("\n[5] Full entity sample (first NM entity):")
    nm_entities = sam_source.search_by_naics("315210", state="NM", limit=1)
    if nm_entities:
        print(json.dumps(nm_entities[0], indent=2)[:2000])
        print("...")

print("\n" + "="*80)
