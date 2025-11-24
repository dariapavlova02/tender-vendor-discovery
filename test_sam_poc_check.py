"""Simplified test to check if SAM POC contacts exist in DB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import Vendor, VendorContact, get_session


def test_sam_poc_in_db():
    vendors_to_test = [
        {
            "name": "Booz Allen Hamilton Inc.",
            "cage_code": "17038",
        },
        {
            "name": "General Dynamics Information Technology Inc.",
            "cage_code": "0U5D4",
        },
        {
            "name": "CACI International Inc",
            "cage_code": "19273",
        },
    ]
    
    print("=" * 80)
    print("SAM.gov POC Data Check")
    print("Checking if POC contacts are saved in vendor_contacts table")
    print("=" * 80)
    
    for vendor_info in vendors_to_test:
        print(f"\n{'=' * 80}")
        print(f"Vendor: {vendor_info['name']}")
        print(f"CAGE Code: {vendor_info['cage_code']}")
        print(f"{'=' * 80}")
        
        with get_session() as db_session:
            db_vendor = db_session.query(Vendor).filter(
                Vendor.cage_code == vendor_info["cage_code"],
                Vendor.source == "sam_entity"
            ).first()
            
            if not db_vendor:
                print(f"  ✗ Vendor NOT found in SAM.gov database")
                print(f"    → Need to ingest this vendor from SAM.gov API")
                continue
            
            print(f"  ✓ Found vendor in DB:")
            print(f"    ID: {db_vendor.id}")
            print(f"    Legal Name: {db_vendor.legal_name}")
            print(f"    UEI: {db_vendor.uei}")
            print(f"    CAGE: {db_vendor.cage_code}")
            print(f"    Website: {db_vendor.website}")
            
            contacts = db_session.query(VendorContact).filter(
                VendorContact.vendor_id == db_vendor.id
            ).all()
            
            if not contacts:
                print(f"\n  ✗ No contacts found in vendor_contacts table")
                print(f"    → This vendor was ingested BEFORE the POC save logic was added")
                print(f"    → Need to re-ingest from SAM.gov API to get POC data")
            else:
                print(f"\n  ✓ Found {len(contacts)} contact(s):")
                for contact in contacts:
                    print(f"\n    Contact #{contact.id}:")
                    print(f"      Source: {contact.source}")
                    print(f"      Name: {contact.first_name} {contact.last_name}")
                    print(f"      Email: {contact.email or 'N/A'}")
                    print(f"      Phone: {contact.phone or 'N/A'}")
                    print(f"      Confidence: {contact.confidence_score}")
                    print(f"      Verified: {contact.is_verified}")
                    
                sam_pocs = [c for c in contacts if c.source == "sam_gov_poc"]
                if sam_pocs:
                    print(f"\n  ✓ SAM POC contacts: {len(sam_pocs)}")
                else:
                    print(f"\n  ✗ No SAM POC contacts (source='sam_gov_poc')")
    
    print(f"\n{'=' * 80}")
    print("NEXT STEPS")
    print(f"{'=' * 80}")
    print("If no SAM POC contacts found, you need to:")
    print("1. Ensure SAM_API_KEY is set in .env")
    print("2. Run a SAM.gov search to re-ingest these vendors with POC data")
    print("3. The new POC save logic in sam_entity.py will populate vendor_contacts")


if __name__ == "__main__":
    test_sam_poc_in_db()
