from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional
import logging
import csv

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Vendor, VendorGSIN, VendorUNSPSC, VendorContact

logger = logging.getLogger(__name__)


class CanadaAwardNoticesLoader:
    CHUNK_SIZE = 10000
    BATCH_SIZE = 500
    
    def __init__(self, session: Session):
        self.session = session
        self.vendor_cache = {}
        self.gsin_cache = {}
        self.unspsc_cache = {}
        self.contact_cache = {}
        self.created_vendors = {}
        self.stats = {
            "rows_processed": 0,
            "vendors_created": 0,
            "vendors_updated": 0,
            "gsin_codes_added": 0,
            "unspsc_codes_added": 0,
            "contacts_added": 0,
        }
    
    def load_csv(self, csv_path: Path, source_name: str = "canada_award_notices") -> dict:
        logger.info(f"Loading Canada award notices from {csv_path}")
        
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
        
        external_ids = [f"{vd['legal_name']}_{vd['postal_code'] or 'NO_POSTAL'}" 
                       for vd in vendor_aggregates.values()]
        
        stmt = select(Vendor).where(
            Vendor.source == source_name,
            Vendor.external_id.in_(external_ids)
        )
        existing_vendors = {v.external_id: v for v in self.session.execute(stmt).scalars()}
        
        for vendor_key, vendor_data in vendor_aggregates.items():
            external_id = f"{vendor_data['legal_name']}_{vendor_data['postal_code'] or 'NO_POSTAL'}"
            existing_vendor = existing_vendors.get(external_id) or self.created_vendors.get(external_id)
            
            self._upsert_vendor(vendor_data, source_name, external_id, existing_vendor)
            self.stats["rows_processed"] += len(vendor_data["awards"])
        
        self.gsin_cache.clear()
        self.unspsc_cache.clear()
        self.contact_cache.clear()
        
        self.session.commit()
    
    def _aggregate_by_vendor(self, chunk: list) -> dict:
        aggregates = {}
        
        for row in chunk:
            legal_name = self._clean_string(row.get("supplierLegalName-nomLegalFournisseur-eng"))
            postal_code = self._normalize_postal_code(row.get("supplierAddressPostalCode-fournisseurAdresseCodePostal"))
            
            if not legal_name:
                continue
            
            vendor_key = f"{legal_name}|{postal_code or 'NO_POSTAL'}"
            
            if vendor_key not in aggregates:
                aggregates[vendor_key] = {
                    "legal_name": legal_name,
                    "address": self._clean_string(row.get("supplierAddressLine-ligneAdresseFournisseur-eng")),
                    "city": self._clean_string(row.get("supplierAddressCity-fournisseurAdresseVille-eng")),
                    "state": self._clean_string(row.get("supplierAddressProvince-fournisseurAdresseProvince-eng")),
                    "postal_code": postal_code,
                    "country": self._clean_string(row.get("supplierAddressCountry-fournisseurAdressePays-eng")),
                    "gsin_codes": set(),
                    "unspsc_codes": set(),
                    "awards": [],
                    "contact_name": self._clean_string(row.get("contactInfoName-informationsContactNom")),
                    "contact_email": self._clean_string(row.get("contactInfoEmail-informationsContactCourriel")),
                    "contact_phone": self._clean_string(row.get("contactInfoPhone-contactInfoTelephone")),
                }
            
            agg = aggregates[vendor_key]
            
            gsin = self._clean_string(row.get("gsin-nibs"))
            if gsin:
                for code in gsin.split('\n'):
                    code = code.strip()
                    if code:
                        agg["gsin_codes"].add(code)
            
            unspsc = self._clean_string(row.get("unspsc"))
            if unspsc:
                agg["unspsc_codes"].add(unspsc)
            
            contract_amount = self._parse_decimal(row.get("contractAmount-montantContrat"))
            total_value = self._parse_decimal(row.get("totalContractValue-valeurTotaleContrat"))
            award_date = self._parse_date(row.get("contractAwardDate-dateAttributionContrat"))
            end_date = self._parse_date(row.get("contractEndDate-dateFinContrat"))
            
            if contract_amount is not None or total_value is not None or award_date is not None:
                metadata = {
                    "contract_number": self._clean_string(row.get("contractNumber-numeroContrat")),
                    "reference_number": self._clean_string(row.get("referenceNumber-numeroReference")),
                    "procurement_method": self._clean_string(row.get("procurementMethod-methodeApprovisionnement-eng")),
                    "trade_agreements": self._clean_string(row.get("tradeAgreements-accordsCommerciaux-eng")),
                    "award_status": self._clean_string(row.get("awardStatus-attributionStatut-eng")),
                }
                
                agg["awards"].append({
                    "amount": contract_amount,
                    "total_value": total_value,
                    "award_date": award_date,
                    "end_date": end_date,
                    "metadata": metadata,
                })
        
        return aggregates
    
    def _upsert_vendor(self, vendor_data: dict, source_name: str, external_id: str, vendor: Optional[Vendor]):
        awards = vendor_data["awards"]
        award_amounts = [a["amount"] for a in awards if a["amount"] is not None]
        total_values = [a["total_value"] for a in awards if a["total_value"] is not None]
        award_dates = [a["award_date"] for a in awards if a["award_date"] is not None]
        end_dates = [a["end_date"] for a in awards if a["end_date"] is not None]
        
        amount_sum = sum(award_amounts) if award_amounts else None
        total_sum = sum(total_values) if total_values else None
        contract_value = total_sum or amount_sum
        
        award_count = len(awards)
        first_date = min(award_dates) if award_dates else None
        last_date = max(award_dates) if award_dates else None
        latest_end_date = max(end_dates) if end_dates else None
        
        if vendor:
            if contract_value and vendor.total_contract_value:
                vendor.total_contract_value += float(contract_value)
            elif contract_value:
                vendor.total_contract_value = float(contract_value)
            
            if award_count:
                vendor.contract_count = (vendor.contract_count or 0) + award_count
            
            if first_date and (not vendor.first_contract_date or first_date < vendor.first_contract_date):
                vendor.first_contract_date = first_date
            
            if last_date and (not vendor.last_contract_date or last_date > vendor.last_contract_date):
                vendor.last_contract_date = last_date
            
            if vendor_data.get("address") and not vendor.address:
                vendor.address = vendor_data["address"]
            if vendor_data.get("city") and not vendor.city:
                vendor.city = vendor_data["city"]
            if vendor_data.get("state") and not vendor.state:
                vendor.state = vendor_data["state"]
            if vendor_data.get("country") and not vendor.country:
                vendor.country = vendor_data["country"]
            
            vendor.updated_at = datetime.utcnow()
            self.stats["vendors_updated"] += 1
        else:
            vendor = Vendor(
                source=source_name,
                external_id=external_id,
                legal_name=vendor_data["legal_name"],
                address=vendor_data.get("address"),
                city=vendor_data.get("city"),
                state=vendor_data.get("state"),
                postal_code=vendor_data.get("postal_code"),
                country=vendor_data.get("country") or "CA",
                total_contract_value=float(contract_value) if contract_value else None,
                contract_count=award_count if award_count else None,
                first_contract_date=first_date,
                last_contract_date=last_date,
                contract_history_json=[
                    {
                        "amount": float(a["amount"]) if a["amount"] else None,
                        "total_value": float(a["total_value"]) if a["total_value"] else None,
                        "award_date": a["award_date"].isoformat() if a["award_date"] else None,
                        "end_date": a["end_date"].isoformat() if a["end_date"] else None,
                        "metadata": a["metadata"],
                    }
                    for a in awards[:100]
                ],
            )
            self.session.add(vendor)
            self.session.flush()
            self.created_vendors[external_id] = vendor
            self.stats["vendors_created"] += 1
        
        if vendor_data["gsin_codes"]:
            self._batch_add_gsin(vendor, vendor_data["gsin_codes"])
        
        if vendor_data["unspsc_codes"]:
            self._batch_add_unspsc(vendor, vendor_data["unspsc_codes"])
        
        if vendor_data.get("contact_email") or vendor_data.get("contact_phone"):
            self._add_contact(vendor, vendor_data, source_name)
    
    def _batch_add_gsin(self, vendor: Vendor, gsin_codes: set):
        codes_to_check = []
        for code in gsin_codes:
            cache_key = f"{vendor.id}:{code}"
            if cache_key not in self.gsin_cache:
                codes_to_check.append(code)
                self.gsin_cache[cache_key] = True
        
        if not codes_to_check:
            return
        
        stmt = select(VendorGSIN.gsin_code).where(
            VendorGSIN.vendor_id == vendor.id,
            VendorGSIN.gsin_code.in_(codes_to_check)
        )
        existing_codes = {row[0] for row in self.session.execute(stmt)}
        
        new_gsins = []
        for code in codes_to_check:
            if code not in existing_codes:
                new_gsins.append(VendorGSIN(
                    vendor_id=vendor.id,
                    gsin_code=code,
                    is_primary=False,
                ))
        
        if new_gsins:
            self.session.add_all(new_gsins)
            self.stats["gsin_codes_added"] += len(new_gsins)
    
    def _batch_add_unspsc(self, vendor: Vendor, unspsc_codes: set):
        codes_to_check = []
        for code in unspsc_codes:
            cache_key = f"{vendor.id}:{code}"
            if cache_key not in self.unspsc_cache:
                codes_to_check.append(code)
                self.unspsc_cache[cache_key] = True
        
        if not codes_to_check:
            return
        
        stmt = select(VendorUNSPSC.unspsc_code).where(
            VendorUNSPSC.vendor_id == vendor.id,
            VendorUNSPSC.unspsc_code.in_(codes_to_check)
        )
        existing_codes = {row[0] for row in self.session.execute(stmt)}
        
        new_unspsc = []
        for code in codes_to_check:
            if code not in existing_codes:
                new_unspsc.append(VendorUNSPSC(
                    vendor_id=vendor.id,
                    unspsc_code=code,
                    is_primary=False,
                ))
        
        if new_unspsc:
            self.session.add_all(new_unspsc)
            self.stats["unspsc_codes_added"] += len(new_unspsc)
    
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
        if value is None or value == "" or (isinstance(value, float) and value != value):
            return None
        return str(value).strip()
    
    @staticmethod
    def _parse_decimal(value) -> Optional[Decimal]:
        if value is None or value == "" or (isinstance(value, float) and value != value):
            return None
        try:
            return Decimal(str(value))
        except:
            return None
    
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
    
    @staticmethod
    def _normalize_postal_code(value) -> Optional[str]:
        if value is None or value == "" or (isinstance(value, float) and value != value):
            return None
        cleaned = str(value).strip().replace(' ', '').upper()
        return cleaned[:6] if cleaned else None


def load_award_notices(session: Session, csv_path: str) -> dict:
    loader = CanadaAwardNoticesLoader(session)
    return loader.load_csv(Path(csv_path))
