"""Logic for ingesting SAM.gov CSV exports into the database."""
import csv
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from ..database import get_session, Vendor, VendorNAICS, VendorContact
from ..models import ContactInfo

logger = logging.getLogger(__name__)

def ingest_sam_csv(csv_path: Path) -> int:
    """
    Reads a SAM.gov CSV export and upserts vendors into the database.
    Returns the number of vendors processed.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    count = 0
    with get_session() as session:
        with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            
            # Normalize headers (sometimes they have different cases or spaces)
            # We'll assume standard SAM.gov export headers for now
            
            for row in reader:
                try:
                    _process_row(session, row)
                    count += 1
                    if count % 100 == 0:
                        session.commit()
                        logger.info(f"Processed {count} vendors...")
                except Exception as e:
                    logger.error(f"Error processing row {count + 1}: {e}")
                    continue
            
            session.commit()
    
    return count

def _process_row(session: Session, row: Dict[str, str]) -> None:
    """Parses a single CSV row and updates the database."""
    
    # Mapping based on standard SAM public export
    # Adjust keys based on actual CSV headers provided by user if needed
    
    uei = row.get("UNIQUE ENTITY ID") or row.get("UEI")
    if not uei:
        return # Skip if no UEI
        
    legal_name = row.get("LEGAL BUSINESS NAME") or row.get("Legal Business Name")
    if not legal_name:
        return

    cage_code = row.get("CAGE CODE") or row.get("CAGE Code")
    duns = row.get("DUNS NUMBER") # Often empty in new exports
    
    # Address
    address_line = row.get("PHYSICAL ADDRESS LINE 1")
    city = row.get("PHYSICAL ADDRESS CITY")
    state = row.get("PHYSICAL ADDRESS PROVINCE OR STATE")
    zip_code = row.get("PHYSICAL ADDRESS ZIP/POSTAL CODE")
    country = row.get("PHYSICAL ADDRESS COUNTRY CODE")
    
    # Business Types (often a delimited string)
    # SAM CSVs might have "BUSINESS TYPES" or boolean columns
    # For now, we'll look for a generic column or infer from others
    business_types_raw = row.get("BUSINESS TYPES") or ""
    business_types = [bt.strip() for bt in business_types_raw.split("~") if bt.strip()]
    
    # Flags
    is_small = "Small Business" in business_types or row.get("SMALL BUSINESS") == "Y"
    is_woman = "Woman Owned" in business_types or row.get("WOMAN OWNED") == "Y"
    # ... add other flags as needed
    
    # Upsert Vendor
    vendor = session.query(Vendor).filter(Vendor.source == "sam_entity", Vendor.external_id == uei).first()
    
    if not vendor:
        vendor = Vendor(
            source="sam_entity",
            external_id=uei,
            created_at=datetime.utcnow()
        )
        session.add(vendor)
    
    vendor.uei = uei
    vendor.duns = duns
    vendor.cage_code = cage_code
    vendor.legal_name = legal_name
    vendor.dba_name = row.get("DBA NAME")
    vendor.country = country
    vendor.state = state
    vendor.city = city
    vendor.address = address_line
    vendor.postal_code = zip_code
    vendor.business_types = business_types
    vendor.is_small_business = is_small
    vendor.is_woman_owned = is_woman
    vendor.updated_at = datetime.utcnow()
    vendor.last_enriched_at = datetime.utcnow() # Mark as enriched since we have details
    
    # NAICS
    naics_string = row.get("NAICS CODES") or row.get("NAICS CODE")
    if naics_string:
        # Clear existing NAICS to avoid duplicates/stale data
        # In a real scenario, we might want to merge, but overwrite is safer for sync
        for n in vendor.naics_codes:
            session.delete(n)
            
        codes = [c.strip() for c in naics_string.split("~") if c.strip()]
        primary_naics = row.get("PRIMARY NAICS")
        
        for code in codes:
            session.add(VendorNAICS(
                vendor=vendor,
                naics_code=code,
                is_primary=(code == primary_naics)
            ))

    # POC
    # CSVs usually have "GOVT BUS POC NAME", "GOVT BUS POC EMAIL", etc.
    poc_name = row.get("GOVT BUS POC NAME") or row.get("GOVERNMENT BUSINESS POC NAME")
    poc_email = row.get("GOVT BUS POC EMAIL") or row.get("GOVERNMENT BUSINESS POC EMAIL")
    poc_phone = row.get("GOVT BUS POC US PHONE") or row.get("GOVERNMENT BUSINESS POC US PHONE")
    
    if poc_email:
        # Check if contact exists
        contact = session.query(VendorContact).filter(VendorContact.vendor_id == vendor.id, VendorContact.email == poc_email).first()
        if not contact:
            contact = VendorContact(
                vendor=vendor,
                source="sam_csv",
                email=poc_email,
                created_at=datetime.utcnow()
            )
            session.add(contact)
        
        contact.first_name = poc_name # Simple assignment, splitting name is risky
        contact.phone = poc_phone
        contact.updated_at = datetime.utcnow()

