"""Update a single existing vendor with POC data from SAM.gov API."""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os
import requests

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import get_session, Vendor, VendorContact

print("=" * 80)
print("Update Single Vendor POC from SAM.gov")
print("=" * 80)

api_key = os.getenv("SAM_API_KEY")
if not api_key:
    print("\n❌ SAM_API_KEY not found")
    sys.exit(1)

print(f"\n✓ API key found")

# Get an existing vendor
with get_session() as db:
    vendor = db.query(Vendor).filter(
        Vendor.source == 'sam_entity',
        Vendor.uei.isnot(None)
    ).first()
    
    if not vendor:
        print("\n❌ No SAM vendors in DB")
        sys.exit(1)
    
    # Store data before session closes
    vendor_id = vendor.id
    vendor_name = vendor.legal_name
    vendor_uei = vendor.uei
    vendor_cage = vendor.cage_code
    
    print(f"\nVendor to update:")
    print(f"  Name: {vendor_name}")
    print(f"  UEI: {vendor_uei}")
    print(f"  CAGE: {vendor_cage}")
    print(f"  ID: {vendor_id}")

# Fetch entity details from SAM.gov
print(f"\nFetching entity details from SAM.gov...")
url = f"https://api.sam.gov/entity-information/v3/entities"
params = {
    "api_key": api_key,
    "ueiSAM": vendor_uei,
    "includeSections": "entityRegistration,coreData"
}

try:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    entities = data.get("entityData", [])
    if not entities:
        print(f"\n⚠️  No entity data returned for UEI {vendor.uei}")
        print(f"Response: {data}")
        sys.exit(1)
    
    entity = entities[0]
    print(f"\n✓ Entity data retrieved")
    
    # Extract POC
    points_of_contact = entity.get("entityRegistration", {}).get("pointsOfContact", {})
    print(f"\nPoints of Contact in API response:")
    print(f"  governmentBusinessPOC: {'Yes' if points_of_contact.get('governmentBusinessPOC') else 'No'}")
    print(f"  electronicBusinessPOC: {'Yes' if points_of_contact.get('electronicBusinessPOC') else 'No'}")
    print(f"  pastPerformancePOC: {'Yes' if points_of_contact.get('pastPerformancePOC') else 'No'}")
    
    if not points_of_contact:
        print(f"\n⚠️  No POC data in API response")
        sys.exit(0)
    
    poc = (points_of_contact.get("governmentBusinessPOC") or 
           points_of_contact.get("electronicBusinessPOC") or 
           points_of_contact.get("pastPerformancePOC"))
    
    if not poc:
        print(f"\n⚠️  All POC fields are None")
        sys.exit(0)
    
    print(f"\nPOC Details:")
    print(f"  First Name: {poc.get('firstName', 'N/A')}")
    print(f"  Last Name: {poc.get('lastName', 'N/A')}")
    print(f"  Email: {poc.get('email', 'N/A')}")
    print(f"  Phone: {poc.get('usPhone', 'N/A')}")
    
    if not poc.get("email") and not poc.get("usPhone"):
        print(f"\n⚠️  POC has no email or phone")
        sys.exit(0)
    
    # Save to DB
    print(f"\nSaving POC to vendor_contacts table...")
    with get_session() as db:
        # Check if contact already exists
        existing = db.query(VendorContact).filter(
            VendorContact.vendor_id == vendor_id,
            VendorContact.source == "sam_gov_poc"
        ).first()
        
        if existing:
            print(f"\n⚠️  POC already exists (ID: {existing.id}), skipping")
        else:
            poc_type = "governmentBusinessPOC" if points_of_contact.get("governmentBusinessPOC") else \
                       "electronicBusinessPOC" if points_of_contact.get("electronicBusinessPOC") else \
                       "pastPerformancePOC"
            
            contact = VendorContact(
                vendor_id=vendor_id,
                source="sam_gov_poc",
                first_name=poc.get("firstName"),
                last_name=poc.get("lastName"),
                email=poc.get("email"),
                phone=poc.get("usPhone"),
                is_verified=True,
                confidence_score=90,
                metadata_json={"poc_type": poc_type}
            )
            db.add(contact)
            db.commit()
            
            print(f"\n✅ POC contact saved!")
            print(f"   Contact ID: {contact.id}")
            print(f"   Source: {contact.source}")
            print(f"   Name: {contact.first_name} {contact.last_name}")
            print(f"   Email: {contact.email or 'N/A'}")
            print(f"   Phone: {contact.phone or 'N/A'}")
    
    # Verify
    print(f"\n" + "=" * 80)
    print("Verification")
    print("=" * 80)
    
    with get_session() as db:
        poc_count = db.query(VendorContact).filter(
            VendorContact.source == "sam_gov_poc"
        ).count()
        print(f"\nTotal SAM POC contacts in DB: {poc_count}")
        
        if poc_count > 0:
            print(f"\n🎉 SUCCESS! POC save logic works!")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
