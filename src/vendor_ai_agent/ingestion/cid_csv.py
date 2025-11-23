"""Logic for ingesting Canadian Importers Database (CID) CSV exports."""
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session

from ..database import get_session, Vendor, VendorNAICS
from ..models import ContactInfo

logger = logging.getLogger(__name__)

def ingest_cid_csv(csv_path: Path) -> int:
    """
    Reads a CID CSV export and upserts vendors into the database.
    Expected columns: HS Code, HS Code Description, Importer Name, City, Province, Country, etc.
    Returns the number of vendors processed.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    count = 0
    with get_session() as session:
        with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    _process_cid_row(session, row)
                    count += 1
                    if count % 100 == 0:
                        session.commit()
                        logger.info(f"Processed {count} CID records...")
                except Exception as e:
                    logger.error(f"Error processing CID row {count + 1}: {e}")
                    continue
            
            session.commit()
    
    return count

def _process_cid_row(session: Session, row: Dict[str, str]) -> None:
    """Parses a single CID CSV row and updates the database."""
    
    # CID CSVs usually have:
    # "HS Code", "HS Description", "Importer Name", "City", "Province", "Postal Code"
    
    importer_name = row.get("Importer Name") or row.get("Name")
    if not importer_name:
        return

    # Generate a deterministic external_id since CID doesn't have a unique ID per vendor
    # We'll use "cid_" + normalized name + city
    city = row.get("City", "").strip()
    province = row.get("Province", "").strip()
    
    normalized_name = importer_name.strip().lower().replace(" ", "_")
    normalized_city = city.lower().replace(" ", "_")
    external_id = f"cid_{normalized_name}_{normalized_city}"[:255]
    
    vendor = session.query(Vendor).filter(Vendor.source == "cid_importers", Vendor.external_id == external_id).first()
    
    if not vendor:
        vendor = Vendor(
            source="cid_importers",
            external_id=external_id,
            created_at=datetime.utcnow()
        )
        session.add(vendor)
    
    vendor.legal_name = importer_name
    vendor.city = city
    vendor.state = province
    vendor.country = "CA" # CID is Canadian Importers
    vendor.postal_code = row.get("Postal Code")
    
    # Mark as importer
    if "cid_importer" not in vendor.enrichment_flags:
        vendor.enrichment_flags.append("cid_importer")
        
    vendor.updated_at = datetime.utcnow()
    
    # HS Codes - we can store them in metadata_json for now as we don't have a VendorProduct table yet
    hs_code = row.get("HS Code")
    hs_desc = row.get("HS Description") or row.get("Description")
    
    if hs_code:
        meta = vendor.metadata_json or {}
        if "imported_products" not in meta:
            meta["imported_products"] = []
        
        # Avoid duplicates
        product_entry = {"hs_code": hs_code, "description": hs_desc}
        if product_entry not in meta["imported_products"]:
            meta["imported_products"].append(product_entry)
            
        vendor.metadata_json = meta

