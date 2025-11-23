"""Logic for ingesting Canadian Company Capabilities (CCC) data."""
import csv
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from ..database import get_session, Vendor, VendorNAICS
from ..models import ContactInfo

logger = logging.getLogger(__name__)

def ingest_ccc_data(file_path: Path) -> int:
    """
    Reads a CCC export (CSV or JSON) and upserts vendors.
    Returns the number of vendors processed.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    count = 0
    with get_session() as session:
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        try:
                            _process_ccc_item(session, item)
                            count += 1
                        except Exception as e:
                            logger.error(f"Error processing CCC item: {e}")
                else:
                    logger.error("JSON root must be a list")
        else:
            # Assume CSV
            with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        _process_ccc_item(session, row)
                        count += 1
                    except Exception as e:
                        logger.error(f"Error processing CCC row: {e}")
        
        session.commit()
    
    return count

def _process_ccc_item(session: Session, item: Dict[str, Any]) -> None:
    """Parses a single CCC record and updates the database."""
    
    # Expected fields (based on typical CCC profile):
    # Name, City, Province, Description, NAICS (list or string), Export Markets, Contact Name, Contact Email
    
    legal_name = item.get("Company Name") or item.get("Name") or item.get("legal_name")
    if not legal_name:
        return

    # Deterministic ID
    city = (item.get("City") or item.get("city") or "").strip()
    province = (item.get("Province") or item.get("province") or "").strip()
    
    normalized_name = str(legal_name).strip().lower().replace(" ", "_")
    normalized_city = city.lower().replace(" ", "_")
    external_id = f"ccc_{normalized_name}_{normalized_city}"[:255]
    
    vendor = session.query(Vendor).filter(Vendor.source == "ccc_capabilities", Vendor.external_id == external_id).first()
    
    if not vendor:
        vendor = Vendor(
            source="ccc_capabilities",
            external_id=external_id,
            created_at=datetime.utcnow()
        )
        session.add(vendor)
    
    vendor.legal_name = legal_name
    vendor.city = city
    vendor.state = province
    vendor.country = "CA"
    vendor.website = item.get("Website") or item.get("website")
    
    # Description / Capabilities
    description = item.get("Description") or item.get("description") or item.get("Products/Services")
    
    meta = vendor.metadata_json or {}
    if description:
        meta["description"] = description
        
    export_markets = item.get("Export Markets") or item.get("export_markets")
    if export_markets:
        meta["export_markets"] = export_markets
        
    vendor.metadata_json = meta
    vendor.updated_at = datetime.utcnow()
    
    # NAICS
    naics_raw = item.get("NAICS") or item.get("naics")
    if naics_raw:
        # Clear old
        for n in vendor.naics_codes:
            session.delete(n)
            
        codes = []
        if isinstance(naics_raw, list):
            codes = naics_raw
        elif isinstance(naics_raw, str):
            codes = [c.strip() for c in naics_raw.split(",") if c.strip()]
            
        for code in codes:
            # CCC often has just codes or "Code - Desc"
            clean_code = str(code).split("-")[0].strip()
            session.add(VendorNAICS(
                vendor=vendor,
                naics_code=clean_code,
                is_primary=False
            ))

