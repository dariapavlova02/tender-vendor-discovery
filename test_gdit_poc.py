"""Test specific vendor POC update - GDIT."""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os
import requests

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import get_session, Vendor, VendorContact

print("=" * 80)
print("Testing POC Fetch for General Dynamics IT")
print("=" * 80)

api_key = os.getenv("SAM_API_KEY")
if not api_key:
    print("\n❌ SAM_API_KEY not found")
    sys.exit(1)

# GDIT UEI from DB
target_uei = "LJGYHYD2NX15"

with get_session() as db:
    vendor = db.query(Vendor).filter(Vendor.uei == target_uei).first()
    
    if vendor:
        vendor_id = vendor.id
        vendor_name = vendor.legal_name
        print(f"\n✓ Vendor found in DB:")
        print(f"  Name: {vendor_name}")
        print(f"  ID: {vendor_id}")
    else:
        print(f"\n⚠️  Vendor with UEI {target_uei} not in DB")
        vendor_id = None
        vendor_name = "General Dynamics IT"

print(f"\nFetching POC from SAM.gov for UEI: {target_uei}...")

url = "https://api.sam.gov/entity-information/v3/entities"
params = {
    "api_key": api_key,
    "ueiSAM": target_uei,
    "includeSections": "entityRegistration,coreData"
}

try:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    entities = data.get("entityData", [])
    if not entities:
        print(f"\n❌ No data returned from SAM.gov")
        print(f"Response: {data}")
        sys.exit(1)
    
    entity = entities[0]
    print(f"✓ Entity data retrieved")
    
    # Check POC
    poc_data = entity.get("entityRegistration", {}).get("pointsOfContact", {})
    
    print(f"\nPOC Fields Present:")
    for poc_type in ["governmentBusinessPOC", "electronicBusinessPOC", "pastPerformancePOC"]:
        poc = poc_data.get(poc_type)
        if poc:
            print(f"\n  {poc_type}:")
            print(f"    First Name: {poc.get('firstName', 'N/A')}")
            print(f"    Last Name: {poc.get('lastName', 'N/A')}")
            print(f"    Email: {poc.get('email', 'N/A')}")
            print(f"    Phone: {poc.get('usPhone', 'N/A')}")
        else:
            print(f"  {poc_type}: Not present")
    
    # Try to save
    best_poc = (poc_data.get("governmentBusinessPOC") or 
                poc_data.get("electronicBusinessPOC") or 
                poc_data.get("pastPerformancePOC"))
    
    if not best_poc:
        print(f"\n⚠️  No POC data available for this entity")
        sys.exit(0)
    
    if not best_poc.get("email") and not best_poc.get("usPhone"):
        print(f"\n⚠️  POC has no contact info (email/phone)")
        sys.exit(0)
    
    if not vendor_id:
        print(f"\n⚠️  Vendor not in DB, cannot save contact")
        sys.exit(0)
    
    # Save
    print(f"\nSaving POC to database...")
    with get_session() as db:
        existing = db.query(VendorContact).filter(
            VendorContact.vendor_id == vendor_id,
            VendorContact.source == "sam_gov_poc"
        ).first()
        
        if existing:
            print(f"⚠️  POC already exists (ID: {existing.id})")
        else:
            poc_type_name = "governmentBusinessPOC" if poc_data.get("governmentBusinessPOC") else \
                           "electronicBusinessPOC" if poc_data.get("electronicBusinessPOC") else \
                           "pastPerformancePOC"
            
            contact = VendorContact(
                vendor_id=vendor_id,
                source="sam_gov_poc",
                first_name=best_poc.get("firstName"),
                last_name=best_poc.get("lastName"),
                email=best_poc.get("email"),
                phone=best_poc.get("usPhone"),
                is_verified=True,
                confidence_score=90,
                metadata_json={"poc_type": poc_type_name}
            )
            db.add(contact)
            db.commit()
            
            print(f"✅ POC saved! Contact ID: {contact.id}")
    
    # Verify
    print(f"\n" + "=" * 80)
    print("Verification")
    print("=" * 80)
    
    with get_session() as db:
        total_poc = db.query(VendorContact).filter(
            VendorContact.source == "sam_gov_poc"
        ).count()
        
        print(f"\nTotal SAM POC contacts in DB: {total_poc}")
        
        if total_poc > 0:
            print(f"🎉 SUCCESS! POC persistence is working!")
            
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
