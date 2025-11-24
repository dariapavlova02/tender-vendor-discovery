from typing import Optional

import requests

from ..models import VendorRecord, ContactInfo
from .base import BaseEnrichmentProvider


class SbaEnrichmentProvider(BaseEnrichmentProvider):
    
    BASE_URL = "https://search.certifications.sba.gov/_api/v2/search"
    
    def __init__(self):
        super().__init__(name="sba_dsbs_enrichment")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def fetch_by_uei(self, uei: str) -> Optional[dict]:
        if not uei:
            return None
        
        payload = {
            "search": uei,
            "filter": {},
            "limit": 10,
            "offset": 0
        }
        
        try:
            response = self.session.post(
                self.BASE_URL,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            for company in results:
                if company.get("uei") == uei:
                    return company
            
            return None
            
        except Exception as e:
            print(f"Error fetching SBA data for UEI {uei}: {e}")
            return None
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if not vendor.uei:
            return vendor
        
        if vendor.email and vendor.primary_contact and vendor.primary_contact.email:
            return vendor
        
        sba_data = self.fetch_by_uei(vendor.uei)
        if not sba_data:
            return vendor
        
        enrichment_applied = False
        
        email = sba_data.get("email")
        phone = sba_data.get("phone")
        poc_name = sba_data.get("poc_name") or sba_data.get("contact_name")
        
        if not vendor.email and email:
            vendor.email = email
            enrichment_applied = True
        
        if not vendor.phone and phone:
            vendor.phone = phone
            enrichment_applied = True
        
        if not vendor.primary_contact and (email or phone or poc_name):
            vendor.primary_contact = ContactInfo(
                name=poc_name,
                email=email,
                phone=phone,
                organization=vendor.company_name
            )
            enrichment_applied = True
        elif vendor.primary_contact:
            if not vendor.primary_contact.email and email:
                vendor.primary_contact.email = email
                enrichment_applied = True
            if not vendor.primary_contact.phone and phone:
                vendor.primary_contact.phone = phone
                enrichment_applied = True
            if not vendor.primary_contact.name and poc_name:
                vendor.primary_contact.name = poc_name
                enrichment_applied = True
        
        certifications = sba_data.get("certifications", [])
        if certifications:
            for cert in certifications:
                cert_name = cert.get("certification_name", "")
                if cert_name and cert_name not in vendor.business_types:
                    vendor.business_types.append(cert_name)
                    enrichment_applied = True
        
        if enrichment_applied:
            if "sba_enriched" not in vendor.enrichment_flags:
                vendor.enrichment_flags.append("sba_enriched")
        
        return vendor
