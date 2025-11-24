"""Simple SAM.gov API test to check POC persistence."""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import Vendor, VendorContact, get_session
from vendor_ai_agent.sources.sam_entity import SamEntitySource
from vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata, PlaceOfPerformance

print("=" * 80, flush=True)
print("SAM.gov POC Test - Simplified", flush=True)
print("=" * 80, flush=True)

api_key = os.getenv("SAM_API_KEY")
print(f"\nAPI Key present: {bool(api_key)}", flush=True)

if not api_key:
    print("ERROR: SAM_API_KEY not found", flush=True)
    sys.exit(1)

print("\nCreating TenderProfile...", flush=True)
profile = TenderProfile(
    tender_id="test_poc",
    country="US",
    api_metadata=APIMetadata(
        codes=CodesMetadata(naics=["541512"]),
        place_of_performance=PlaceOfPerformance(state_province="VA")
    )
)

print("Initializing SAM source...", flush=True)
sam_source = SamEntitySource(
    api_key=api_key,
    use_cache=False,
    sync_to_db=True
)

print("\nCalling SAM.gov API (this may take 30-60 seconds)...", flush=True)
try:
    vendors = sam_source.search(profile)
    print(f"\n✓ API call succeeded! Found {len(vendors)} vendors", flush=True)
    
    print("\nFirst 3 vendors:", flush=True)
    for i, v in enumerate(vendors[:3], 1):
        print(f"  {i}. {v.company_name}", flush=True)
        print(f"     UEI: {v.uei}", flush=True)
        print(f"     CAGE: {v.cage_code}", flush=True)
        
except Exception as e:
    print(f"\n✗ API call failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80, flush=True)
print("Checking database for SAM POC contacts...", flush=True)
print("=" * 80, flush=True)

with get_session() as db:
    poc_contacts = db.query(VendorContact).filter(
        VendorContact.source == "sam_gov_poc"
    ).all()
    
    print(f"\nSAM POC contacts in DB: {len(poc_contacts)}", flush=True)
    
    if poc_contacts:
        print("\n🎉 SUCCESS! POC data was saved!", flush=True)
        for contact in poc_contacts[:3]:
            vendor = db.query(Vendor).filter(Vendor.id == contact.vendor_id).first()
            print(f"\n  Vendor: {vendor.company_name if vendor else 'Unknown'}", flush=True)
            print(f"  Contact: {contact.first_name} {contact.last_name}", flush=True)
            print(f"  Email: {contact.email or 'N/A'}", flush=True)
            print(f"  Phone: {contact.phone or 'N/A'}", flush=True)
    else:
        print("\n⚠️  No SAM POC contacts found", flush=True)
        print("Checking if vendors were saved at all...", flush=True)
        
        recent_vendors = db.query(Vendor).filter(
            Vendor.source == "sam_entity"
        ).order_by(Vendor.created_at.desc()).limit(3).all()
        
        print(f"\nRecent SAM vendors: {len(recent_vendors)}", flush=True)
        for v in recent_vendors:
            print(f"  - {v.company_name} (UEI: {v.uei})", flush=True)
            contacts = db.query(VendorContact).filter(
                VendorContact.vendor_id == v.id
            ).all()
            print(f"    Contacts in DB: {len(contacts)}", flush=True)
            for c in contacts:
                print(f"      Source: {c.source}, Name: {c.first_name} {c.last_name}", flush=True)

print("\n" + "=" * 80, flush=True)
print("Test complete!", flush=True)
print("=" * 80, flush=True)
