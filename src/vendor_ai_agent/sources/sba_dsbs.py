import json
import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

import requests
from sqlalchemy.orm import Session

from ..database import Vendor, VendorNAICS, VendorContact, get_session
from ..models import TenderProfile, VendorRecord, ContactInfo
from .base import BaseVendorSource


class SbaDsbsSource(BaseVendorSource):
    
    BASE_URL = "https://search.certifications.sba.gov/_api/v2/search"
    
    CERT_CODES = {
        "hubzone": 3,
        "wosb": 5,
        "edwosb": 6,
    }
    
    def __init__(
        self,
        use_cache: bool = True,
        sync_to_db: bool = True,
        max_results_per_query: int = 1000
    ):
        super().__init__(name="sba_dsbs")
        self.use_cache = use_cache
        self.sync_to_db = sync_to_db
        self.max_results_per_query = max_results_per_query
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def is_compatible(self, profile: TenderProfile) -> bool:
        country = profile.dynamic_context.country if profile.dynamic_context else None
        
        if country and country != "US":
            return False
        
        set_aside_code = profile.api_metadata.set_aside.code if profile.api_metadata.set_aside else None
        set_aside_desc = profile.api_metadata.set_aside.description if profile.api_metadata.set_aside else None
        
        if set_aside_code or set_aside_desc:
            set_aside_text = f"{set_aside_code or ''} {set_aside_desc or ''}".lower()
            if any(cert in set_aside_text for cert in ["wosb", "edwosb", "hubzone"]):
                return True
        
        naics_codes = profile.api_metadata.codes.naics or []
        if not naics_codes:
            return False
        
        return True
    
    def _make_request(self, payload: dict) -> dict:
        try:
            response = self.session.post(
                self.BASE_URL,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"SBA DSBS API request failed: {e}")
    
    def search_by_certification(
        self,
        cert_code: int,
        naics_codes: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        state: Optional[str] = None,
        active_sam: bool = True,
        limit: int = 1000
    ) -> List[dict]:
        print(f"Searching SBA DSBS for certification code {cert_code}...")
        
        payload = {
            "search": search_term or "",
            "filter": {
                "certification": [cert_code],
                "isActiveSAM": active_sam
            },
            "limit": min(limit, self.max_results_per_query),
            "offset": 0,
            "sort": {"businessName": "asc"}
        }
        
        if naics_codes:
            naics_objects = []
            for code in naics_codes:
                if len(code) == 6:
                    naics_objects.append({
                        "label": f"NAICS {code}",
                        "value": code
                    })
            
            if naics_objects:
                payload["filter"]["naics_codes"] = naics_objects
                payload["filter"]["isPrimary"] = False
        
        try:
            data = self._make_request(payload)
            results = data.get("results", [])
            total = data.get("estimatedTotalHits", 0)
            
            print(f"Found {len(results)} results (total: {total})")
            
            if state:
                print(f"Post-filtering by state: {state}")
                filtered = []
                for company in results:
                    company_state = company.get("sam_address_state_province")
                    if company_state == state:
                        filtered.append(company)
                print(f"Filtered to {len(filtered)} companies in {state}")
                results = filtered
            
            return results
            
        except Exception as e:
            print(f"Error searching SBA DSBS: {e}")
            return []
    
    def search_by_naics(
        self,
        naics_codes: List[str],
        cert_code: Optional[int] = None,
        active_sam: bool = False,
        state: Optional[str] = None,
        limit: int = 1000
    ) -> List[dict]:
        print(f"Searching SBA DSBS by NAICS codes: {naics_codes}")
        
        naics_objects = []
        for code in naics_codes:
            if len(code) == 6:
                naics_objects.append({
                    "label": f"NAICS {code}",
                    "value": code
                })
        
        if not naics_objects:
            print("No valid 6-digit NAICS codes provided")
            return []
        
        payload = {
            "search": "",
            "filter": {
                "naics_codes": naics_objects,
                "isPrimary": False,
                "isActiveSAM": active_sam
            },
            "limit": min(limit, self.max_results_per_query),
            "offset": 0,
            "sort": {"businessName": "asc"}
        }
        
        if cert_code:
            payload["filter"]["certification"] = [cert_code]
        
        try:
            data = self._make_request(payload)
            results = data.get("results", [])
            total = data.get("estimatedTotalHits", 0)
            
            print(f"Found {len(results)} results (total: {total})")
            
            if state:
                print(f"Post-filtering by state: {state}")
                filtered = []
                for company in results:
                    company_state = company.get("sam_address_state_province")
                    if company_state == state:
                        filtered.append(company)
                print(f"Filtered to {len(filtered)} companies in {state}")
                results = filtered
            
            return results
            
        except Exception as e:
            print(f"Error searching SBA DSBS by NAICS: {e}")
            return []
    
    def fetch_by_uei(self, uei: str) -> Optional[dict]:
        payload = {
            "search": uei,
            "filter": {},
            "limit": 10,
            "offset": 0
        }
        
        try:
            data = self._make_request(payload)
            results = data.get("results", [])
            
            for company in results:
                if company.get("uei") == uei:
                    return company
            
            return None
            
        except Exception as e:
            print(f"Error fetching SBA DSBS company by UEI {uei}: {e}")
            return None
    
    def _parse_company(self, company_data: dict) -> Optional[Vendor]:
        try:
            uei = company_data.get("uei")
            cage_code = company_data.get("cage_code")
            legal_name = company_data.get("businessName", "")
            dba_name = company_data.get("dba_name")
            
            if not uei and not legal_name:
                return None
            
            website = company_data.get("url")
            if website and not website.startswith("http"):
                website = f"https://{website}"
            
            state = company_data.get("sam_address_state_province")
            city = company_data.get("sam_address_city")
            address = company_data.get("sam_address_line_1")
            postal_code = company_data.get("sam_address_zip_postal_code")
            country = company_data.get("sam_address_country_code", "US")
            
            certifications = company_data.get("certifications", [])
            business_types = []
            
            is_wosb = False
            is_edwosb = False
            is_hubzone = False
            is_8a = False
            is_vosb = False
            is_sdvosb = False
            
            for cert in certifications:
                cert_name = cert.get("certification_name", "")
                business_types.append(cert_name)
                
                cert_lower = cert_name.lower()
                if "wosb" in cert_lower and "edwosb" not in cert_lower:
                    is_wosb = True
                if "edwosb" in cert_lower:
                    is_edwosb = True
                    is_wosb = True
                if "hubzone" in cert_lower:
                    is_hubzone = True
                if "8(a)" in cert_lower:
                    is_8a = True
                if "vosb" in cert_lower and "sdvosb" not in cert_lower:
                    is_vosb = True
                if "sdvosb" in cert_lower:
                    is_sdvosb = True
            
            self_certs = company_data.get("self_certifications", [])
            for cert_obj in self_certs:
                cert_type = cert_obj.get("certification_type", "")
                if cert_type:
                    business_types.append(f"Self-Cert: {cert_type}")
            
            vendor = Vendor(
                source=self.name,
                external_id=uei or cage_code,
                uei=uei,
                duns=None,
                cage_code=cage_code,
                legal_name=legal_name,
                dba_name=dba_name,
                website=website,
                country=country,
                state=state,
                city=city,
                address=address,
                postal_code=postal_code,
                business_types=business_types,
                is_small_business=True,
                is_woman_owned=is_wosb or is_edwosb,
                is_veteran_owned=is_vosb or is_sdvosb,
                is_minority_owned=False,
                is_8a=is_8a,
                is_hubzone=is_hubzone,
                metadata_json=json.dumps(company_data),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return vendor
            
        except Exception as e:
            print(f"Error parsing SBA DSBS company: {e}")
            return None
    
    def _company_to_vendor_record(self, company_data: dict) -> Optional[VendorRecord]:
        vendor = self._parse_company(company_data)
        if not vendor:
            return None
        
        email = company_data.get("email")
        phone = company_data.get("phone")
        
        contact_info = None
        poc_name = company_data.get("poc_name") or company_data.get("contact_name")
        if email or phone or poc_name:
            contact_info = ContactInfo(
                name=poc_name,
                email=email,
                phone=phone,
                organization=vendor.legal_name
            )
        
        business_types_list = []
        if vendor.business_types:
            if isinstance(vendor.business_types, list):
                business_types_list = vendor.business_types
            elif isinstance(vendor.business_types, str):
                business_types_list = [vendor.business_types]
        
        enrichment_flags = ["sba_certified"]
        if company_data.get("samRegistered"):
            enrichment_flags.append("sam_registered")
        
        return VendorRecord(
            company_name=vendor.legal_name,
            website=vendor.website,
            email=contact_info.email if contact_info else None,
            phone=contact_info.phone if contact_info else None,
            location=f"{vendor.city}, {vendor.state}" if vendor.city and vendor.state else vendor.state,
            city=vendor.city,
            state=vendor.state,
            country=vendor.country,
            industry=None,
            source=self.name,
            is_past_winner=False,
            enrichment_flags=enrichment_flags,
            uei=vendor.uei,
            duns=vendor.duns,
            cage_code=vendor.cage_code,
            business_types=business_types_list,
            primary_contact=contact_info,
            total_contract_value=vendor.total_contract_value,
            contract_count=vendor.contract_count,
        )
    
    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        if not self.is_compatible(profile):
            return []
        
        naics_codes = profile.api_metadata.codes.naics or []
        if not naics_codes:
            return []
        
        set_aside_code = profile.api_metadata.set_aside.code if profile.api_metadata.set_aside else None
        set_aside_desc = profile.api_metadata.set_aside.description if profile.api_metadata.set_aside else None
        set_aside_text = f"{set_aside_code or ''} {set_aside_desc or ''}".lower() if (set_aside_code or set_aside_desc) else ""
        
        cert_code = None
        if "edwosb" in set_aside_text:
            cert_code = self.CERT_CODES["edwosb"]
        elif "wosb" in set_aside_text:
            cert_code = self.CERT_CODES["wosb"]
        elif "hubzone" in set_aside_text:
            cert_code = self.CERT_CODES["hubzone"]
        
        state = None
        if profile.country == "US":
            state = profile.api_metadata.place_of_performance.state_province
        
        vendors = []
        
        with get_session() as db_session:
            if cert_code:
                try:
                    companies = self.search_by_certification(
                        cert_code=cert_code,
                        naics_codes=naics_codes[:3],
                        state=state,
                        active_sam=True,
                        limit=100
                    )
                    
                    for company_data in companies:
                        if self.sync_to_db:
                            self._sync_to_db(company_data, db_session)
                        
                        vendor_record = self._company_to_vendor_record(company_data)
                        if vendor_record:
                            vendors.append(vendor_record)
                    
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"Error searching SBA DSBS: {e}")
            else:
                for naics_code in naics_codes[:3]:
                    try:
                        companies = self.search_by_naics(
                            naics_codes=[naics_code],
                            active_sam=True,
                            state=state,
                            limit=50
                        )
                        
                        for company_data in companies:
                            if self.sync_to_db:
                                self._sync_to_db(company_data, db_session)
                            
                            vendor_record = self._company_to_vendor_record(company_data)
                            if vendor_record:
                                vendors.append(vendor_record)
                        
                        time.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Error searching SBA DSBS for NAICS {naics_code}: {e}")
                        continue
        
        return vendors[:100]
    
    def _sync_to_db(self, company_data: dict, db_session: Session) -> None:
        try:
            vendor_obj = self._parse_company(company_data)
            if not vendor_obj:
                return
            
            existing = db_session.query(Vendor).filter(
                Vendor.source == self.name,
                Vendor.external_id == vendor_obj.external_id
            ).first()
            
            if existing:
                existing.updated_at = datetime.utcnow()
                existing.metadata_json = json.dumps(company_data)
            else:
                db_session.add(vendor_obj)
                db_session.flush()
                
                naics_list = company_data.get("naics_codes", [])
                primary_naics = company_data.get("naics_primary")
                
                for naics_item in naics_list:
                    if isinstance(naics_item, dict):
                        naics_code = naics_item.get("naics_code", "")
                        naics_desc = naics_item.get("naics_description", "")
                    else:
                        naics_code = str(naics_item)
                        naics_desc = None
                    
                    if naics_code:
                        naics_obj = VendorNAICS(
                            vendor_id=vendor_obj.id,
                            naics_code=naics_code,
                            naics_description=naics_desc,
                            is_primary=(naics_code == primary_naics)
                        )
                        db_session.add(naics_obj)
                
                email = company_data.get("email")
                phone = company_data.get("phone")
                poc_name = company_data.get("poc_name") or company_data.get("contact_name")
                
                if email or phone:
                    contact_obj = VendorContact(
                        vendor_id=vendor_obj.id,
                        source="sba_dsbs",
                        first_name=poc_name.split()[0] if poc_name else None,
                        last_name=" ".join(poc_name.split()[1:]) if poc_name and len(poc_name.split()) > 1 else None,
                        email=email,
                        phone=phone,
                        is_verified=True,
                        confidence_score=85,
                        metadata_json=json.dumps({"source": "sba_dsbs"})
                    )
                    db_session.add(contact_obj)
            
            db_session.commit()
            
        except Exception as e:
            print(f"Error syncing SBA DSBS company to DB: {e}")
            db_session.rollback()
