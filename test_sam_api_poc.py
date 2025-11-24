"""Test SAM.gov API to ingest a vendor with POC data and verify it's saved."""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import Vendor, VendorContact, get_session
from vendor_ai_agent.sources.sam_entity import SamEntitySource
from vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata, PlaceOfPerformance


def test_sam_api_poc_ingestion():
    print("=" * 80)
    print("SAM.gov API POC Ingestion Test")
    print("Testing if POC data is saved to vendor_contacts table")
    print("=" * 80)
    
    api_key = os.getenv("SAM_API_KEY")
    if not api_key:
        print("\n❌ SAM_API_KEY not found in environment")
        print("   Export it with: export SAM_API_KEY='your_key_here'")
        return
    
    print(f"\n✓ SAM_API_KEY found")
    
    test_naics = "541512"
    test_state = "VA"
    
    print(f"\nSearching SAM.gov for:")
    print(f"  NAICS: {test_naics} (Computer Systems Design Services)")
    print(f"  State: {test_state}")
    print(f"  Limit: 5 vendors")
    
    profile = TenderProfile(
        tender_id="test_poc_ingestion",
        country="US",
        api_metadata=APIMetadata(
            codes=CodesMetadata(naics=[test_naics]),
            place_of_performance=PlaceOfPerformance(state_province=test_state)
        )
    )
    
    sam_source = SamEntitySource(
        api_key=api_key,
        use_cache=False,
        sync_to_db=True
    )
    
    print(f"\n{'=' * 80}")
    print("Calling SAM.gov API...")
    print(f"{'=' * 80}")
    
    vendors = sam_source.search(profile)
    
    print(f"\n✓ Found {len(vendors)} vendors from SAM.gov API")
    
    with get_session() as db_session:
        for i, vendor in enumerate(vendors[:5], 1):
            print(f"\n{'=' * 80}")
            print(f"Vendor #{i}: {vendor.company_name}")
            print(f"{'=' * 80}")
            print(f"  UEI: {vendor.uei}")
            print(f"  CAGE: {vendor.cage_code}")
            print(f"  Website: {vendor.website}")
            
            db_vendor = db_session.query(Vendor).filter(
                Vendor.source == "sam_entity",
                Vendor.uei == vendor.uei
            ).first()
            
            if not db_vendor:
                print(f"  ✗ Vendor not found in DB (sync_to_db failed?)")
                continue
            
            print(f"  ✓ Vendor found in DB (ID: {db_vendor.id})")
            
            contacts = db_session.query(VendorContact).filter(
                VendorContact.vendor_id == db_vendor.id
            ).all()
            
            if not contacts:
                print(f"\n  ⚠️  No contacts in vendor_contacts table")
                print(f"     → POC save logic might not have triggered")
                print(f"     → Or vendor has no POC data in SAM.gov")
            else:
                print(f"\n  ✓ Found {len(contacts)} contact(s) in DB:")
                for contact in contacts:
                    print(f"\n    Contact #{contact.id}:")
                    print(f"      Source: {contact.source}")
                    print(f"      Name: {contact.first_name} {contact.last_name}")
                    print(f"      Email: {contact.email or 'N/A'}")
                    print(f"      Phone: {contact.phone or 'N/A'}")
                    print(f"      Confidence: {contact.confidence_score}")
                    
                    if contact.source == "sam_gov_poc":
                        print(f"      ✅ THIS IS A SAM POC CONTACT!")
    
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    
    with get_session() as db_session:
        sam_poc_count = db_session.query(VendorContact).filter(
            VendorContact.source == "sam_gov_poc"
        ).count()
        
        print(f"Total SAM POC contacts in DB: {sam_poc_count}")
        
        if sam_poc_count > 0:
            print(f"\n🎉 SUCCESS! POC save logic is working!")
            print(f"   sam_entity.py is now saving POC data to vendor_contacts")
        else:
            print(f"\n❌ FAILED: No SAM POC contacts saved")
            print(f"   Check if:")
            print(f"   1. SAM.gov API returns POC data in response")
            print(f"   2. POC save logic in sam_entity.py is correct")
            print(f"   3. Database transaction is committing properly")


if __name__ == "__main__":
    test_sam_api_poc_ingestion()
