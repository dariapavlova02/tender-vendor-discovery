"""Diagnostic test to determine SAM.gov API access level and POC data availability."""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os
import requests
import json

load_dotenv()

print("=" * 80)
print("SAM.gov API Access Level Diagnostic")
print("=" * 80)

api_key = os.getenv("SAM_API_KEY")
if not api_key:
    print("\n❌ SAM_API_KEY not found in .env")
    sys.exit(1)

print(f"\n✓ API Key found (length: {len(api_key)})")

# Test cases: Different entity types
test_entities = [
    {
        "name": "General Dynamics IT (Large Contractor)",
        "uei": "LJGYHYD2NX15",
        "expected": "Large defense contractor - likely has POC if available"
    },
    {
        "name": "Small Business Example",
        "uei": "JF19T52GRAM5",  # Random small business UEI
        "expected": "Small business - may have public POC"
    }
]

base_url = "https://api.sam.gov/entity-information/v3/entities"

# Test different includeSections configurations
test_configs = [
    {
        "name": "Config 1: Current (entityRegistration + coreData)",
        "sections": "entityRegistration,coreData"
    },
    {
        "name": "Config 2: Explicit pointsOfContact",
        "sections": "pointsOfContact"
    },
    {
        "name": "Config 3: All sections",
        "sections": "entityRegistration,coreData,pointsOfContact,assertions"
    }
]

results = []

for entity in test_entities[:1]:  # Start with GDIT only
    print(f"\n{'=' * 80}")
    print(f"Testing: {entity['name']}")
    print(f"UEI: {entity['uei']}")
    print(f"{'=' * 80}")
    
    for config in test_configs:
        print(f"\n--- {config['name']} ---")
        
        params = {
            "api_key": api_key,
            "ueiSAM": entity['uei'],
            "includeSections": config['sections']
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                entities_data = data.get("entityData", [])
                
                if not entities_data:
                    print("❌ No entity data returned")
                    results.append({
                        "entity": entity['name'],
                        "config": config['name'],
                        "status": "no_data",
                        "poc_available": False
                    })
                    continue
                
                entity_data = entities_data[0]
                
                # Check for POC in different locations
                poc_found = False
                poc_details = {}
                
                # Location 1: entityRegistration.pointsOfContact
                entity_reg = entity_data.get("entityRegistration", {})
                points_of_contact = entity_reg.get("pointsOfContact", {})
                
                if points_of_contact:
                    print(f"✓ pointsOfContact structure found!")
                    print(f"\nAvailable POC types:")
                    
                    for poc_type in ["governmentBusinessPOC", "electronicBusinessPOC", "pastPerformancePOC", "altElectronicBusinessPOC"]:
                        poc = points_of_contact.get(poc_type)
                        if poc:
                            print(f"\n  {poc_type}:")
                            print(f"    Structure exists: ✓")
                            
                            # Check what fields are present
                            fields = {
                                "firstName": poc.get("firstName"),
                                "lastName": poc.get("lastName"),
                                "email": poc.get("email"),
                                "usPhone": poc.get("usPhone"),
                                "title": poc.get("title"),
                                "address": poc.get("address")
                            }
                            
                            for field, value in fields.items():
                                if value:
                                    print(f"    {field}: '{value[:50] if isinstance(value, str) else value}'")
                                    poc_found = True
                                else:
                                    print(f"    {field}: [NOT PRESENT]")
                            
                            poc_details[poc_type] = fields
                        else:
                            print(f"\n  {poc_type}: [NOT PRESENT]")
                    
                    results.append({
                        "entity": entity['name'],
                        "config": config['name'],
                        "status": "success",
                        "poc_available": poc_found,
                        "poc_types": list(poc_details.keys()),
                        "has_email": any(p.get("email") for p in poc_details.values()),
                        "has_phone": any(p.get("usPhone") for p in poc_details.values())
                    })
                else:
                    print("❌ No pointsOfContact structure in response")
                    print(f"\nTop-level keys in entityRegistration:")
                    for key in entity_reg.keys():
                        print(f"  - {key}")
                    
                    results.append({
                        "entity": entity['name'],
                        "config": config['name'],
                        "status": "no_poc_structure",
                        "poc_available": False
                    })
                
            elif response.status_code == 401:
                print("❌ 401 Unauthorized - API key invalid or expired")
                results.append({
                    "entity": entity['name'],
                    "config": config['name'],
                    "status": "unauthorized",
                    "poc_available": False
                })
            elif response.status_code == 403:
                print("❌ 403 Forbidden - Insufficient permissions (FOUO access required?)")
                results.append({
                    "entity": entity['name'],
                    "config": config['name'],
                    "status": "forbidden",
                    "poc_available": False,
                    "note": "May require FOUO access level"
                })
            else:
                print(f"❌ Unexpected status: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                results.append({
                    "entity": entity['name'],
                    "config": config['name'],
                    "status": f"error_{response.status_code}",
                    "poc_available": False
                })
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            results.append({
                "entity": entity['name'],
                "config": config['name'],
                "status": "exception",
                "error": str(e),
                "poc_available": False
            })

# Summary
print(f"\n\n{'=' * 80}")
print("DIAGNOSTIC SUMMARY")
print(f"{'=' * 80}\n")

print("Results by configuration:")
for result in results:
    print(f"\n{result['config']}:")
    print(f"  Status: {result['status']}")
    print(f"  POC Data Available: {result['poc_available']}")
    if result.get('has_email') is not None:
        print(f"  Has Email: {result['has_email']}")
        print(f"  Has Phone: {result['has_phone']}")
    if result.get('note'):
        print(f"  Note: {result['note']}")

# Conclusion
print(f"\n{'=' * 80}")
print("CONCLUSION")
print(f"{'=' * 80}\n")

any_poc_found = any(r['poc_available'] for r in results)
any_email_found = any(r.get('has_email', False) for r in results)

if any_email_found:
    print("✅ POC contact data (email/phone) IS accessible with your API key!")
    print("   → Next step: Update sam_entity.py to use the working includeSections")
elif any_poc_found:
    print("⚠️  POC structure exists but email/phone fields are NOT populated")
    print("   → This indicates FOUO (For Official Use Only) access is required")
    print("   → Your API key has Public access level")
    print("   → To get POC emails/phones, you need:")
    print("     1. Register a Federal System Account at SAM.gov")
    print("     2. Request 'Read FOUO' permission")
    print("     3. Configure IP whitelist")
else:
    print("❌ No POC data structure found in any configuration")
    print("   → Possible reasons:")
    print("     1. API key is Public level (most likely)")
    print("     2. Entity simply doesn't have POC registered")
    print("     3. Different API endpoint needed")

print("\n" + "=" * 80)
