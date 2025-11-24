"""
ODBus Municipal Business Directory Loader

Dataset: Aggregated Canadian business directory from 67+ municipal/provincial sources
Source: Statistics Canada Open Data Business (ODBus_v1)
Updated: 2025
Format: CSV (32 columns, 446,576 rows)

Coverage:
- Provinces: AB, BC, MB, NB, NT, ON
- Major cities: Calgary, Edmonton, Vancouver, Toronto, Ottawa, Hamilton, Winnipeg
- License types: Business licenses, food establishments, trade contractors, pharmacies

Key Fields:
- business_name, alt_business_name
- business_sector, business_subsector, business_description
- derived_NAICS, source_NAICS_primary, source_NAICS_secondary
- full_address, postal_code, city, prov_terr
- latitude, longitude
- provider (source municipality/province)
- licence_number, licence_type

Note: Missing values represented as ".."
Expected: ~400K+ unique businesses after deduplication
"""

import csv
import json
from typing import Dict, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database.models import Vendor, VendorNAICS
from ..database.connection import get_session


class CanadaODBusLoader:
    def __init__(self):
        self.source = "canada_odbus"
        self.stats = {
            "rows_processed": 0,
            "vendors_created": 0,
            "vendors_updated": 0,
            "vendors_skipped": 0,
            "duplicates_detected": 0,
        }
        self.seen_businesses = {}
    
    def _normalize_value(self, value) -> Optional[str]:
        if not value or value == "..":
            return None
        value_str = str(value).strip()
        return value_str if value_str else None
    
    def _create_external_id(self, business_name: str, city: str, postal_code: Optional[str]) -> str:
        normalized_name = business_name.strip().upper()
        
        if postal_code:
            normalized_postal = postal_code.strip().upper().replace(" ", "")
            return f"{normalized_name}_{normalized_postal}_ODBUS"
        else:
            normalized_city = city.strip().upper().replace(" ", "_")
            return f"{normalized_name}_{normalized_city}_ODBUS"
    
    def _parse_row(self, row: dict) -> Optional[dict]:
        business_name = self._normalize_value(row.get("business_name"))
        city = self._normalize_value(row.get("city"))
        
        if not business_name or not city:
            return None
        
        postal_code = self._normalize_value(row.get("postal_code"))
        prov_terr = self._normalize_value(row.get("prov_terr"))
        

        
        derived_naics = self._normalize_value(row.get("derived_NAICS"))
        source_naics_primary = self._normalize_value(row.get("source_NAICS_primary"))
        source_naics_secondary = self._normalize_value(row.get("source_NAICS_secondary"))
        
        naics_codes = []
        seen_normalized = set()
        
        for code in [derived_naics, source_naics_primary, source_naics_secondary]:
            if code:
                normalized = str(code).strip().split('.')[0]
                if normalized and normalized not in seen_normalized:
                    seen_normalized.add(normalized)
                    naics_codes.append(normalized)
        
        return {
            "business_name": business_name,
            "alt_business_name": self._normalize_value(row.get("alt_business_name")),
            "business_sector": self._normalize_value(row.get("business_sector")),
            "business_subsector": self._normalize_value(row.get("business_subsector")),
            "business_description": self._normalize_value(row.get("business_description")),
            "naics_codes": naics_codes,
            "naics_descr": self._normalize_value(row.get("NAICS_descr")),
            "naics_descr2": self._normalize_value(row.get("NAICS_descr2")),
            "full_address": self._normalize_value(row.get("full_address")),
            "postal_code": postal_code,
            "city": city,
            "prov_terr": prov_terr,
            "latitude": self._normalize_value(row.get("latitude")),
            "longitude": self._normalize_value(row.get("longitude")),
            "provider": self._normalize_value(row.get("provider")),
            "licence_number": self._normalize_value(row.get("licence_number")),
            "licence_type": self._normalize_value(row.get("licence_type")),
            "status": self._normalize_value(row.get("status")),
            "total_no_employees": self._normalize_value(row.get("total_no_employees")),
        }
    
    def _upsert_vendor(
        self,
        session: Session,
        data: dict,
    ) -> bool:
        external_id = self._create_external_id(
            data["business_name"],
            data["city"],
            data["postal_code"]
        )
        
        if external_id in self.seen_businesses:
            self.stats["duplicates_detected"] += 1
            return False
        
        self.seen_businesses[external_id] = True
        
        stmt = select(Vendor).where(
            Vendor.external_id == external_id,
            Vendor.source == self.source
        )
        existing = session.execute(stmt).scalar_one_or_none()
        
        metadata_json = {
            "business_sector": data["business_sector"],
            "business_subsector": data["business_subsector"],
            "business_description": data["business_description"],
            "provider": data["provider"],
            "licence_type": data["licence_type"],
            "licence_number": data["licence_number"],
            "status": data["status"],
            "total_no_employees": data["total_no_employees"],
            "naics_descr": data["naics_descr"],
            "naics_descr2": data["naics_descr2"],
            "latitude": data["latitude"],
            "longitude": data["longitude"],
        }
        
        metadata_json = {k: v for k, v in metadata_json.items() if v is not None}
        
        if existing:
            existing.metadata_json = json.dumps(metadata_json)
            
            if data["naics_codes"]:
                existing_codes = {n.naics_code for n in existing.naics_codes}
                for idx, code in enumerate(data["naics_codes"]):
                    if code not in existing_codes:
                        naics = VendorNAICS(
                            naics_code=code,
                            is_primary=(idx == 0 and not existing.naics_codes)
                        )
                        existing.naics_codes.append(naics)
            
            if data["full_address"]:
                existing.address = data["full_address"]
            if data["city"]:
                existing.city = data["city"]
            if data["prov_terr"]:
                existing.state = data["prov_terr"]
            if data["postal_code"]:
                existing.postal_code = data["postal_code"]
            
            self.stats["vendors_updated"] += 1
        else:
            vendor = Vendor(
                external_id=external_id,
                legal_name=data["business_name"],
                dba_name=data["alt_business_name"],
                source=self.source,
                address=data["full_address"],
                city=data["city"],
                state=data["prov_terr"],
                postal_code=data["postal_code"],
                country="CA",
                metadata_json=json.dumps(metadata_json),
            )
            
            if data["naics_codes"]:
                seen_codes = set()
                for idx, code in enumerate(data["naics_codes"]):
                    if code not in seen_codes:
                        seen_codes.add(code)
                        naics = VendorNAICS(
                            naics_code=code,
                            is_primary=(idx == 0)
                        )
                        vendor.naics_codes.append(naics)
            
            session.add(vendor)
            self.stats["vendors_created"] += 1
        
        return True
    
    def load(self, session: Session, csv_path: str, batch_size: int = 10000) -> dict:
        print(f"Loading ODBus data from: {csv_path}")
        print(f"Batch size: {batch_size:,}")
        
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                self.stats["rows_processed"] += 1
                
                if self.stats["rows_processed"] % batch_size == 0:
                    session.commit()
                    print(f"Processed {self.stats['rows_processed']:,} rows | "
                          f"Created: {self.stats['vendors_created']:,} | "
                          f"Updated: {self.stats['vendors_updated']:,} | "
                          f"Duplicates: {self.stats['duplicates_detected']:,}")
                
                data = self._parse_row(row)
                if not data:
                    self.stats["vendors_skipped"] += 1
                    continue
                
                self._upsert_vendor(session, data)
        
        session.commit()
        print(f"Completed: {self.stats['vendors_created']} created, {self.stats['vendors_updated']} updated")
        
        return self.stats


def load_odbus(session: Session, csv_path: str) -> dict:
    loader = CanadaODBusLoader()
    return loader.load(session, csv_path)


if __name__ == "__main__":
    csv_path = "data/canada_sources/ODBus_v1/ODBus_v1.csv"
    
    with get_session() as session:
        stats = load_odbus(session, csv_path)
        
        print("\n" + "=" * 80)
        print("INGESTION COMPLETE")
        print("=" * 80)
        print(f"Rows processed:         {stats['rows_processed']:,}")
        print(f"Vendors created:        {stats['vendors_created']:,}")
        print(f"Vendors updated:        {stats['vendors_updated']:,}")
        print(f"Vendors skipped:        {stats['vendors_skipped']:,}")
        print(f"Duplicates detected:    {stats['duplicates_detected']:,}")
        print("=" * 80)
