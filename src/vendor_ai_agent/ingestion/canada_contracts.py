from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional
import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Vendor, VendorGSIN, VendorUNSPSC, VendorContact

logger = logging.getLogger(__name__)


class CanadaContractsLoader:
    CHUNK_SIZE = 10000
    BATCH_SIZE = 500
    
    def __init__(self, session: Session):
        self.session = session
        self.vendor_cache = {}
        self.gsin_cache = {}
        self.unspsc_cache = {}
        self.contact_cache = {}
        self.stats = {
            "rows_processed": 0,
            "vendors_created": 0,
            "vendors_updated": 0,
            "gsin_codes_added": 0,
            "unspsc_codes_added": 0,
            "contacts_added": 0,
        }
    
    def load_csv(self, csv_path: Path, source_name: str = "canada_contracts") -> dict:
        logger.info(f"Loading Canada contracts from {csv_path}")
        
        for chunk in pd.read_csv(
            csv_path,
            chunksize=self.CHUNK_SIZE,
            low_memory=False,
            encoding="utf-8-sig",
            on_bad_lines="skip",
            encoding_errors="ignore"
        ):
            self._process_chunk(chunk, source_name)
            self.session.commit()
            
            logger.info(
                f"Processed {self.stats['rows_processed']} rows, "
                f"{self.stats['vendors_created']} vendors created, "
                f"{self.stats['vendors_updated']} updated"
            )
        
        logger.info(f"Completed loading: {self.stats}")
        return self.stats
    
    def _process_chunk(self, chunk: pd.DataFrame, source_name: str):
        vendor_aggregates = self._aggregate_by_vendor(chunk)
        
        # Process all vendors and relationships
        for vendor_key, vendor_data in vendor_aggregates.items():
            self._upsert_vendor(vendor_data, source_name)
            self.stats["rows_processed"] += len(vendor_data["contracts"])
        
        # Flush once at the end of chunk to ensure all IDs are available
        self.session.flush()
    
    def _aggregate_by_vendor(self, chunk: pd.DataFrame) -> dict:
        aggregates = {}
        
        for _, row in chunk.iterrows():
            legal_name = self._clean_string(row.get("supplierLegalName-nomLegalFournisseur-eng"))
            standardized_name = self._clean_string(row.get("supplierStandardizedName-nomNormaliseFournisseur-eng"))
            postal_code = self._clean_string(row.get("supplierAddressPostalCode-fournisseurAdresseCodePostal"))
            
            if not standardized_name and not legal_name:
                continue
            
            vendor_name = standardized_name or legal_name
            vendor_key = f"{vendor_name}|{postal_code or 'NO_POSTAL'}"
            
            if vendor_key not in aggregates:
                aggregates[vendor_key] = {
                    "legal_name": legal_name or standardized_name,
                    "standardized_name": standardized_name,
                    "address": self._clean_string(row.get("supplierAddressLine-ligneAdresseFournisseur-eng")),
                    "city": self._clean_string(row.get("supplierAddressCity-fournisseurAdresseVille-eng")),
                    "state": self._clean_string(row.get("supplierAddressProvince-fournisseurAdresseProvince-eng")),
                    "postal_code": postal_code,
                    "country": "CA",
                    "employee_count_range": self._clean_string(row.get("supplierEmployeeCount-fournisseurNombreEmployes-eng")),
                    "gsin_codes": set(),
                    "unspsc_codes": set(),
                    "contracts": [],
                    "contact_name": self._clean_string(row.get("contactInfoName-informationsContactNom")),
                    "contact_email": self._clean_string(row.get("contactInfoEmail-informationsContactCourriel")),
                    "contact_phone": self._clean_string(row.get("contactInfoPhone-contactInfoTelephone")),
                }
            
            agg = aggregates[vendor_key]
            
            gsin = self._clean_string(row.get("gsin-nibs"))
            if gsin:
                agg["gsin_codes"].add(gsin)
            
            unspsc = self._clean_string(row.get("unspsc"))
            if unspsc:
                agg["unspsc_codes"].add(unspsc)
            
            contract_value = self._parse_decimal(row.get("totalContractValue-valeurTotaleContrat"))
            contract_date = self._parse_date(row.get("contractAwardDate-dateAttributionContrat"))
            
            if contract_value is not None or contract_date is not None:
                agg["contracts"].append({
                    "value": contract_value,
                    "date": contract_date,
                    "contract_number": self._clean_string(row.get("contractNumber-numeroContrat")),
                    "description": self._clean_string(row.get("tenderDescription-descriptionAppelOffres-eng")),
                    "procurement_category": self._clean_string(row.get("procurementCategory-categorieApprovisionnement")),
                })
        
        return aggregates
    
    def _upsert_vendor(self, vendor_data: dict, source_name: str):
        vendor_name = vendor_data['standardized_name'] or vendor_data['legal_name']
        external_id = f"{vendor_name}_{vendor_data['postal_code'] or 'NO_POSTAL'}"
        
        stmt = select(Vendor).where(
            Vendor.source == source_name,
            Vendor.external_id == external_id
        )
        vendor = self.session.execute(stmt).scalar_one_or_none()
        
        contracts = vendor_data["contracts"]
        contract_values = [c["value"] for c in contracts if c["value"] is not None]
        contract_dates = [c["date"] for c in contracts if c["date"] is not None]
        
        total_value = sum(contract_values) if contract_values else None
        contract_count = len(contracts)
        first_date = min(contract_dates) if contract_dates else None
        last_date = max(contract_dates) if contract_dates else None
        
        if vendor:
            if total_value and vendor.total_contract_value:
                vendor.total_contract_value += float(total_value)
            elif total_value:
                vendor.total_contract_value = float(total_value)
            
            if contract_count:
                vendor.contract_count = (vendor.contract_count or 0) + contract_count
            
            if first_date and (not vendor.first_contract_date or first_date < vendor.first_contract_date):
                vendor.first_contract_date = first_date
            
            if last_date and (not vendor.last_contract_date or last_date > vendor.last_contract_date):
                vendor.last_contract_date = last_date
            
            vendor.updated_at = datetime.utcnow()
            self.stats["vendors_updated"] += 1
        else:
            vendor = Vendor(
                source=source_name,
                external_id=external_id,
                legal_name=vendor_data["legal_name"],
                dba_name=vendor_data.get("standardized_name"),
                address=vendor_data.get("address"),
                city=vendor_data.get("city"),
                state=vendor_data.get("state"),
                postal_code=vendor_data.get("postal_code"),
                country=vendor_data["country"],
                employee_count_range=vendor_data.get("employee_count_range"),
                total_contract_value=float(total_value) if total_value else None,
                contract_count=contract_count if contract_count else None,
                first_contract_date=first_date,
                last_contract_date=last_date,
                contract_history_json=[
                    {
                        "value": float(c["value"]) if c["value"] else None,
                        "date": c["date"].isoformat() if c["date"] else None,
                        "number": c["contract_number"],
                        "description": c["description"],
                        "category": c["procurement_category"],
                    }
                    for c in contracts[:100]
                ],
            )
            self.session.add(vendor)
            # Flush immediately for new vendors so we can get vendor.id
            self.session.flush()
            self.stats["vendors_created"] += 1
        
        for gsin_code in vendor_data["gsin_codes"]:
            self._add_gsin(vendor, gsin_code)
        
        for unspsc_code in vendor_data["unspsc_codes"]:
            self._add_unspsc(vendor, unspsc_code)
        
        if vendor_data.get("contact_email") or vendor_data.get("contact_phone"):
            self._add_contact(vendor, vendor_data, source_name)
    
    def _add_gsin(self, vendor: Vendor, gsin_code: str):
        cache_key = f"{vendor.id}:{gsin_code}"
        
        if cache_key in self.gsin_cache:
            return
        
        stmt = select(VendorGSIN).where(
            VendorGSIN.vendor_id == vendor.id,
            VendorGSIN.gsin_code == gsin_code
        )
        existing = self.session.execute(stmt).scalar_one_or_none()
        
        if not existing:
            vendor_gsin = VendorGSIN(
                vendor_id=vendor.id,
                gsin_code=gsin_code,
                is_primary=False,
            )
            self.session.add(vendor_gsin)
            self.stats["gsin_codes_added"] += 1
        
        self.gsin_cache[cache_key] = True
    
    def _add_unspsc(self, vendor: Vendor, unspsc_code: str):
        cache_key = f"{vendor.id}:{unspsc_code}"
        
        if cache_key in self.unspsc_cache:
            return
        
        stmt = select(VendorUNSPSC).where(
            VendorUNSPSC.vendor_id == vendor.id,
            VendorUNSPSC.unspsc_code == unspsc_code
        )
        existing = self.session.execute(stmt).scalar_one_or_none()
        
        if not existing:
            vendor_unspsc = VendorUNSPSC(
                vendor_id=vendor.id,
                unspsc_code=unspsc_code,
                is_primary=False,
            )
            self.session.add(vendor_unspsc)
            self.stats["unspsc_codes_added"] += 1
        
        self.unspsc_cache[cache_key] = True
    
    def _add_contact(self, vendor: Vendor, vendor_data: dict, source_name: str):
        email = vendor_data.get("contact_email")
        cache_key = f"{vendor.id}:{email or 'no_email'}"
        
        if cache_key in self.contact_cache:
            return
        
        if email:
            stmt = select(VendorContact).where(
                VendorContact.vendor_id == vendor.id,
                VendorContact.email == email
            )
            existing = self.session.execute(stmt).scalar_one_or_none()
            
            if existing:
                self.contact_cache[cache_key] = True
                return
        
        name_parts = (vendor_data.get("contact_name") or "").split(None, 1)
        first_name = name_parts[0] if name_parts else None
        last_name = name_parts[1] if len(name_parts) > 1 else None
        
        contact = VendorContact(
            vendor_id=vendor.id,
            source=source_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=vendor_data.get("contact_phone"),
            is_verified=False,
            confidence_score=60,
        )
        self.session.add(contact)
        self.stats["contacts_added"] += 1
        self.contact_cache[cache_key] = True
    
    @staticmethod
    def _clean_string(value) -> Optional[str]:
        if pd.isna(value) or value == "":
            return None
        return str(value).strip()
    
    @staticmethod
    def _parse_decimal(value) -> Optional[Decimal]:
        if pd.isna(value):
            return None
        try:
            return Decimal(str(value))
        except:
            return None
    
    @staticmethod
    def _parse_date(value) -> Optional[date]:
        if pd.isna(value):
            return None
        try:
            return pd.to_datetime(value).date()
        except:
            return None


def load_canada_contracts(session: Session, csv_path: str) -> dict:
    loader = CanadaContractsLoader(session)
    return loader.load_csv(Path(csv_path))
