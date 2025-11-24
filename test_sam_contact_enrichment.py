"""Test SAM.gov POC contact enrichment on vendors with contact forms (currently failing)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import Vendor, VendorContact, get_session
from vendor_ai_agent.enrichment_providers import SamContactProvider
from vendor_ai_agent.models import VendorRecord


def test_sam_contact_enrichment():
    vendors_to_test = [
        {
            "name": "Booz Allen Hamilton Inc.",
            "website": "https://www.boozallen.com",
            "cage_code": "17038",
        },
        {
            "name": "General Dynamics Information Technology Inc.",
            "website": "https://www.gdit.com",
            "cage_code": "0U5D4",
        },
        {
            "name": "CACI International Inc",
            "website": "https://www.caci.com",
            "cage_code": "19273",
        },
    ]
    
    print("=" * 80)
    print("SAM.gov POC Contact Enrichment Test")
    print("Testing vendors that currently fail web scraping (contact forms only)")
    print("=" * 80)
    
    provider = SamContactProvider()
    results = []
    
    for vendor_info in vendors_to_test:
        print(f"\n{'=' * 80}")
        print(f"Testing: {vendor_info['name']}")
        print(f"Website: {vendor_info['website']}")
        print(f"CAGE Code: {vendor_info['cage_code']}")
        print(f"{'=' * 80}")
        
        with get_session() as db_session:
            db_vendor = db_session.query(Vendor).filter(
                Vendor.cage_code == vendor_info["cage_code"],
                Vendor.source == "sam_entity"
            ).first()
            
            if not db_vendor:
                print(f"  ✗ Vendor not found in SAM.gov database")
                results.append({
                    "vendor": vendor_info["name"],
                    "status": "not_in_db",
                    "email": None,
                    "phone": None
                })
                continue
            
            print(f"  ✓ Found vendor in DB: {db_vendor.legal_name} (ID: {db_vendor.id})")
            print(f"    UEI: {db_vendor.uei}")
            print(f"    CAGE: {db_vendor.cage_code}")
            
            contacts = db_session.query(VendorContact).filter(
                VendorContact.vendor_id == db_vendor.id,
                VendorContact.source == "sam_gov_poc"
            ).all()
            
            if contacts:
                print(f"  ✓ Found {len(contacts)} SAM POC contact(s) in DB:")
                for contact in contacts:
                    print(f"    - Name: {contact.first_name} {contact.last_name}")
                    print(f"      Email: {contact.email or 'N/A'}")
                    print(f"      Phone: {contact.phone or 'N/A'}")
            else:
                print(f"  ✗ No SAM POC contacts found in vendor_contacts table")
                print(f"    (This means sam_entity.py didn't save POC data)")
        
        vendor_record = VendorRecord(
            company_name=vendor_info["name"],
            website=vendor_info["website"],
            email=None,
            phone=None,
            location=None,
            city=None,
            state=None,
            country="US",
            industry=None,
            source="sam_entity",
            is_past_winner=False,
            enrichment_flags=[],
            cage_code=vendor_info["cage_code"]
        )
        
        print(f"\n  Enriching vendor record with SamContactProvider...")
        enriched = provider.enrich(vendor_record)
        
        email_found = enriched.email is not None
        phone_found = enriched.phone is not None
        
        print(f"\n  Results:")
        print(f"    Email: {enriched.email or '❌ Not found'}")
        print(f"    Phone: {enriched.phone or '❌ Not found'}")
        print(f"    Contact name: {enriched.filtering_metadata.get('contact_names', ['N/A'])[0]}")
        print(f"    Enrichment flags: {enriched.enrichment_flags}")
        
        results.append({
            "vendor": vendor_info["name"],
            "status": "success" if (email_found or phone_found) else "no_contacts",
            "email": enriched.email,
            "phone": enriched.phone
        })
    
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    
    total = len(results)
    successful = sum(1 for r in results if r["status"] == "success")
    not_in_db = sum(1 for r in results if r["status"] == "not_in_db")
    no_contacts = sum(1 for r in results if r["status"] == "no_contacts")
    
    print(f"\nTotal vendors tested: {total}")
    print(f"  ✓ Successfully enriched: {successful} ({successful/total*100:.1f}%)")
    print(f"  ✗ Not in SAM.gov DB: {not_in_db}")
    print(f"  ✗ No POC contacts found: {no_contacts}")
    
    print(f"\nDetailed results:")
    for result in results:
        status_icon = "✓" if result["status"] == "success" else "✗"
        print(f"  {status_icon} {result['vendor']}")
        if result["status"] == "success":
            print(f"    Email: {result['email'] or 'N/A'}")
            print(f"    Phone: {result['phone'] or 'N/A'}")
        else:
            print(f"    Status: {result['status']}")
    
    print(f"\n{'=' * 80}")
    print("EXPECTED vs ACTUAL")
    print(f"{'=' * 80}")
    print(f"Previous success rate (web scraping only): 3/6 = 50%")
    print(f"Current success rate (SAM POC + web scraping): {successful}/{total} = {successful/total*100:.1f}%")
    
    if successful == total:
        print(f"\n🎉 SUCCESS! All vendors now have contacts from SAM.gov POC!")
    elif successful > 0:
        print(f"\n✓ Improvement detected, but some vendors still missing POC data")
        print(f"  This likely means those vendors need to be re-ingested from SAM.gov API")
    else:
        print(f"\n❌ No improvement - POC data not being saved to DB")
        print(f"  Check if sam_entity.py changes are working correctly")


if __name__ == "__main__":
    test_sam_contact_enrichment()
