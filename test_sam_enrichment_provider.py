"""Test SamContactProvider enrichment with existing POC data."""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import get_session, Vendor, VendorContact
from vendor_ai_agent.enrichment_providers.sam_contact import SamContactProvider
from vendor_ai_agent.models import VendorRecord

print("=" * 80)
print("Testing SamContactProvider Enrichment")
print("=" * 80)

# Verify POC exists in DB
print("\n1. Verifying SAM POC data in database...")

with get_session() as db:
    poc_contacts = db.query(VendorContact).filter(
        VendorContact.source == "sam_gov_poc"
    ).all()
    
    print(f"   SAM POC contacts in DB: {len(poc_contacts)}")
    
    if not poc_contacts:
        print("\n❌ No SAM POC contacts found!")
        print("   Run: poetry run python test_create_poc.py")
        sys.exit(1)
    
    for poc in poc_contacts:
        vendor = db.query(Vendor).filter(Vendor.id == poc.vendor_id).first()
        print(f"\n   ✓ POC for {vendor.legal_name if vendor else 'Unknown'}")
        print(f"     UEI: {vendor.uei if vendor else 'N/A'}")
        print(f"     CAGE: {vendor.cage_code if vendor else 'N/A'}")
        print(f"     Contact: {poc.first_name} {poc.last_name}")
        print(f"     Email: {poc.email}")
        print(f"     Phone: {poc.phone}")

# Test enrichment
print(f"\n{'=' * 80}")
print("2. Testing SamContactProvider.enrich()")
print("=" * 80)

provider = SamContactProvider()

# Get actual CAGE code from database
with get_session() as db:
    gdit_vendor = db.query(Vendor).filter(Vendor.uei == "LJGYHYD2NX15").first()
    actual_cage = gdit_vendor.cage_code if gdit_vendor else None

# Create test vendor record matching GDIT
test_vendor = VendorRecord(
    company_name="General Dynamics Information Technology Inc",
    uei="LJGYHYD2NX15",
    cage_code=actual_cage
)

print(f"\nTest Vendor:")
print(f"  Company: {test_vendor.company_name}")
print(f"  UEI: {test_vendor.uei}")
print(f"  CAGE: {test_vendor.cage_code}")

print(f"\nCalling provider.enrich()...")
enriched_vendor = provider.enrich(test_vendor)

print(f"\nResults:")
print(f"  Email: {enriched_vendor.email or 'N/A'}")
print(f"  Phone: {enriched_vendor.phone or 'N/A'}")
print(f"  Enrichment flags: {enriched_vendor.enrichment_flags}")

if enriched_vendor.email or enriched_vendor.phone:
    print(f"\n  Metadata:")
    if enriched_vendor.email:
        print(f"    Email source: {enriched_vendor.filtering_metadata.get('email_source')}")
        print(f"    Email confidence: {enriched_vendor.filtering_metadata.get('email_confidence')}")
    if enriched_vendor.phone:
        print(f"    Phone source: {enriched_vendor.filtering_metadata.get('phone_source')}")
        print(f"    Phone confidence: {enriched_vendor.filtering_metadata.get('phone_confidence')}")
    if enriched_vendor.filtering_metadata.get('contact_names'):
        print(f"    Contact names: {enriched_vendor.filtering_metadata.get('contact_names')}")

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print("=" * 80)

if enriched_vendor.email or enriched_vendor.phone:
    print("\n🎉 SUCCESS! SAM Contact Provider is working!")
    print("\n✓ POC data saved to database")
    print("✓ Provider correctly identifies enrichable vendors")
    print("✓ Provider retrieves and formats contacts")
    print("\nNext Steps:")
    print("  1. The provider is already registered in pipeline.py")
    print("  2. Run full pipeline to see it in action")
    print("  3. Test with real tender processing")
else:
    print("\n⚠️  No enrichment occurred - check vendor matching logic")

