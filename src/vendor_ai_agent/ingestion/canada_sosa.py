from datetime import datetime, date
from pathlib import Path
from typing import Optional
import logging
import csv

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Vendor

logger = logging.getLogger(__name__)


class CanadaSOSALoader:
    CHUNK_SIZE = 5000
    BATCH_SIZE = 500
    
    def __init__(self, session: Session):
        self.session = session
        self.vendor_cache = {}
        self.created_vendors = {}
        self.stats = {
            "rows_processed": 0,
            "vendors_created": 0,
            "vendors_updated": 0,
            "standing_offers_added": 0,
        }
    
    def load_csv(self, csv_path: Path, source_name: str = "canada_sosa") -> dict:
        logger.info(f"Loading Canada SOSA from {csv_path}")
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                
                chunk = []
                chunk_num = 0
                
                for row in reader:
                    chunk.append(row)
                    
                    if len(chunk) >= self.CHUNK_SIZE:
                        chunk_num += 1
                        try:
                            logger.info(f"Processing chunk {chunk_num} ({len(chunk)} rows)...")
                            self._process_chunk(chunk, source_name)
                            
                            logger.info(
                                f"Chunk {chunk_num} complete. Total: {self.stats['rows_processed']} rows, "
                                f"{self.stats['vendors_created']} vendors created, "
                                f"{self.stats['vendors_updated']} updated"
                            )
                        except Exception as e:
                            logger.error(f"Error processing chunk {chunk_num}: {e}")
                            self.session.rollback()
                        
                        chunk = []
                
                if chunk:
                    chunk_num += 1
                    try:
                        logger.info(f"Processing final chunk {chunk_num} ({len(chunk)} rows)...")
                        self._process_chunk(chunk, source_name)
                        logger.info(
                            f"Chunk {chunk_num} complete. Total: {self.stats['rows_processed']} rows, "
                            f"{self.stats['vendors_created']} vendors created, "
                            f"{self.stats['vendors_updated']} updated"
                        )
                    except Exception as e:
                        logger.error(f"Error processing final chunk {chunk_num}: {e}")
                        self.session.rollback()
                        
        except Exception as e:
            logger.error(f"Failed to open CSV: {e}")
            raise
        
        logger.info(f"Completed loading: {self.stats}")
        return self.stats
    
    def _process_chunk(self, chunk: list, source_name: str):
        vendor_aggregates = self._aggregate_by_vendor(chunk)
        
        if not vendor_aggregates:
            return
        
        external_ids = [f"{vd['legal_name']}_NO_POSTAL" for vd in vendor_aggregates.values()]
        
        stmt = select(Vendor).where(
            Vendor.source == source_name,
            Vendor.external_id.in_(external_ids)
        )
        existing_vendors = {v.external_id: v for v in self.session.execute(stmt).scalars()}
        
        for vendor_key, vendor_data in vendor_aggregates.items():
            external_id = f"{vendor_data['legal_name']}_NO_POSTAL"
            existing_vendor = existing_vendors.get(external_id) or self.created_vendors.get(external_id)
            
            self._upsert_vendor(vendor_data, source_name, external_id, existing_vendor)
            self.stats["rows_processed"] += len(vendor_data["agreements"])
        
        self.session.commit()
    
    def _aggregate_by_vendor(self, chunk: list) -> dict:
        aggregates = {}
        
        for row in chunk:
            legal_name = self._clean_string(row.get("supplier-legal-name"))
            
            if not legal_name:
                continue
            
            vendor_key = legal_name
            
            if vendor_key not in aggregates:
                aggregates[vendor_key] = {
                    "legal_name": legal_name,
                    "standardized_name": self._clean_string(row.get("supplier-standardized-name")),
                    "operating_names": set(),
                    "agreements": [],
                    "commodity_codes": set(),
                    "country": "CA",
                }
            
            agg = aggregates[vendor_key]
            
            operating_name = self._clean_string(row.get("supplier-operating-name"))
            if operating_name and operating_name != legal_name:
                agg["operating_names"].add(operating_name)
            
            commodity = self._clean_string(row.get("commodity"))
            if commodity:
                agg["commodity_codes"].add(commodity)
            
            agreement_number = self._clean_string(row.get("agreement-number"))
            award_date = self._parse_date(row.get("award-date"))
            expiry_date = self._parse_date(row.get("expiry-date"))
            
            if agreement_number:
                agg["agreements"].append({
                    "agreement_number": agreement_number,
                    "agreement_type": self._clean_string(row.get("agreement-type_en")),
                    "award_date": award_date,
                    "expiry_date": expiry_date,
                    "delivery_point": self._clean_string(row.get("delivery-point_en")),
                    "end_user_entity": self._clean_string(row.get("end-user-entity_en")),
                    "sosa_description": self._clean_string(row.get("sosa-description_en")),
                    "commodity_description": self._clean_string(row.get("commodity-description_en")),
                })
        
        return aggregates
    
    def _upsert_vendor(self, vendor_data: dict, source_name: str, external_id: str, vendor: Optional[Vendor]):
        agreements = vendor_data["agreements"]
        award_dates = [a["award_date"] for a in agreements if a["award_date"] is not None]
        expiry_dates = [a["expiry_date"] for a in agreements if a["expiry_date"] is not None]
        
        first_award = min(award_dates) if award_dates else None
        last_award = max(award_dates) if award_dates else None
        latest_expiry = max(expiry_dates) if expiry_dates else None
        
        standing_offers_data = [
            {
                "agreement_number": a["agreement_number"],
                "agreement_type": a["agreement_type"],
                "award_date": a["award_date"].isoformat() if a["award_date"] else None,
                "expiry_date": a["expiry_date"].isoformat() if a["expiry_date"] else None,
                "delivery_point": a["delivery_point"],
                "end_user_entity": a["end_user_entity"],
                "sosa_description": a["sosa_description"],
                "commodity_description": a["commodity_description"],
            }
            for a in agreements
        ]
        
        metadata = {
            "standing_offers": standing_offers_data,
            "commodity_codes": list(vendor_data["commodity_codes"]),
            "operating_names": list(vendor_data["operating_names"]),
            "is_prequalified": True,
            "prequalification_expiry": latest_expiry.isoformat() if latest_expiry else None,
        }
        
        if vendor:
            if first_award and (not vendor.first_contract_date or first_award < vendor.first_contract_date):
                vendor.first_contract_date = first_award
            
            if last_award and (not vendor.last_contract_date or last_award > vendor.last_contract_date):
                vendor.last_contract_date = last_award
            
            if vendor_data.get("standardized_name") and not vendor.dba_name:
                vendor.dba_name = vendor_data["standardized_name"]
            
            existing_metadata = vendor.metadata_json or {}
            existing_metadata.update(metadata)
            vendor.metadata_json = existing_metadata
            
            vendor.updated_at = datetime.utcnow()
            self.stats["vendors_updated"] += 1
            self.stats["standing_offers_added"] += len(agreements)
        else:
            vendor = Vendor(
                source=source_name,
                external_id=external_id,
                legal_name=vendor_data["legal_name"],
                dba_name=vendor_data.get("standardized_name"),
                country=vendor_data["country"],
                first_contract_date=first_award,
                last_contract_date=last_award,
                contract_count=len(agreements),
                metadata_json=metadata,
            )
            self.session.add(vendor)
            self.session.flush()
            self.created_vendors[external_id] = vendor
            self.stats["vendors_created"] += 1
            self.stats["standing_offers_added"] += len(agreements)
    
    @staticmethod
    def _clean_string(value) -> Optional[str]:
        if value is None or value == "" or (isinstance(value, float) and value != value):
            return None
        return str(value).strip()
    
    @staticmethod
    def _parse_date(value) -> Optional[date]:
        if value is None or value == "" or (isinstance(value, float) and value != value):
            return None
        try:
            from datetime import datetime as dt
            value_str = str(value)
            return dt.strptime(value_str[:10], '%Y-%m-%d').date()
        except:
            return None


def load_sosa(session: Session, csv_path: str) -> dict:
    loader = CanadaSOSALoader(session)
    return loader.load_csv(Path(csv_path))
