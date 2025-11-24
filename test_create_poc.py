"""Create a test SAM POC contact to verify enrichment provider works."""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database import get_session, Vendor, VendorContact

print("=" * 80)
print("Creating Test SAM POC Contact")
print("=" * 80)

# Get GDIT vendor
with get_session() as db:
    vendor = db.query(Vendor).filter(Vendor.uei == "LJGYHYD2NX15").first()
    
    if not vendor:
        print("\n❌ GDIT vendor not found")
        sys.exit(1)
    
    vendor_id = vendor.id
    vendor_name = vendor.legal_name
    vendor_uei = vendor.uei
    
    print(f"\n✓ Target vendor:")
    print(f"  Name: {vendor_name}")
    print(f"  UEI: {vendor_uei}")
    print(f"  ID: {vendor_id}")

# Create test POC contact
print(f"\nCreating test SAM POC contact...")

with get_session() as db:
    # Check if exists
    existing = db.query(VendorContact).filter(
        VendorContact.vendor_id == vendor_id,
        VendorContact.source == "sam_gov_poc"
    ).first()
    
    if existing:
        print(f"\n⚠️  POC already exists (ID: {existing.id})")
        print(f"   Name: {existing.first_name} {existing.last_name}")
        print(f"   Email: {existing.email}")
        print(f"   Phone: {existing.phone}")
    else:
        contact = VendorContact(
            vendor_id=vendor_id,
            source="sam_gov_poc",
            first_name="John",
            last_name="Smith",
            email="john.smith@gdit.com",
            phone="703-555-1234",
            is_verified=True,
            confidence_score=90,
            metadata_json={"poc_type": "governmentBusinessPOC", "note": "Test data for POC validation"}
        )
        db.add(contact)
        db.commit()
        
        print(f"\n✅ Test POC contact created!")
        print(f"   Contact ID: {contact.id}")
        print(f"   Name: {contact.first_name} {contact.last_name}")
        print(f"   Email: {contact.email}")
        print(f"   Phone: {contact.phone}")

# Verify
print(f"\n" + "=" * 80)
print("Database Verification")
print("=" * 80)

with get_session() as db:
    sam_poc_count = db.query(VendorContact).filter(
        VendorContact.source == "sam_gov_poc"
    ).count()
    
    print(f"\nTotal SAM POC contacts: {sam_poc_count}")
    
    if sam_poc_count > 0:
        print(f"\n✓ SAM POC data now exists in database!")
        print(f"\n📋 Next step: Test the SamContactProvider enrichment")
        print(f"   Run: poetry run python test_sam_enrichment_provider.py")

