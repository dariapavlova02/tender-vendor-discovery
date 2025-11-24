from __future__ import annotations

import logging
import re
from typing import Optional

from Levenshtein import ratio
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Vendor, VendorNAICS
from ..models import VendorRecord
from .base import BaseEnrichmentProvider


class CanadaNAICSEnricher(BaseEnrichmentProvider):
    
    LEGAL_SUFFIXES = [
        r'\bINC\.?$', r'\bINCORPORATED$', r'\bCORP\.?$', r'\bCORPORATION$',
        r'\bLTD\.?$', r'\bLIMITED$', r'\bLLC\.?$', r'\bLTÉE\.?$', r'\bLIMITÉE$',
        r'\bCO\.?$', r'\bCOMPANY$', r'\bGMBH$', r'\bSA$', r'\bSARL$',
        r'\bPLC$', r'\bPTY$', r'\bLTDA$', r'\bGROUP$', r'\bENTERPRISES?$'
    ]
    
    def __init__(
        self, 
        db_session: Session,
        similarity_threshold: float = 0.6,
        max_results_per_vendor: int = 5
    ) -> None:
        super().__init__(name="canada_naics_cross_reference")
        self.db_session = db_session
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results_per_vendor
        self.logger = logging.getLogger(__name__)
        
        self.suffix_pattern = re.compile('|'.join(self.LEGAL_SUFFIXES), re.IGNORECASE)

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if self._already_has_naics(vendor):
            self.logger.debug(f"Vendor {vendor.company_name} already has NAICS codes, skipping")
            return vendor
        
        if not vendor.city:
            self.logger.debug(f"Vendor {vendor.company_name} has no city data, cannot match")
            return vendor
        
        if vendor.source not in ["canada_contracts", "canada_award_notices", "canada_pspc_payments"]:
            self.logger.debug(f"Vendor {vendor.company_name} source {vendor.source} not eligible for NAICS enrichment")
            return vendor
        
        self.logger.info(f"Searching NAICS matches for {vendor.company_name} in {vendor.city}")
        
        matching_vendors = self._find_matching_vendors(vendor)
        
        if matching_vendors:
            naics_codes = self._extract_naics_codes(matching_vendors)
            
            if naics_codes:
                vendor.filtering_metadata["naics_codes"] = naics_codes
                vendor.filtering_metadata["naics_source"] = "canada_odbus_cross_reference"
                vendor.filtering_metadata["naics_match_count"] = len(matching_vendors)
                vendor.enrichment_flags.append(self.name)
                
                self.logger.info(f"  ✓ Found {len(naics_codes)} NAICS codes from {len(matching_vendors)} matching vendors")
        else:
            self.logger.debug(f"  ✗ No matching vendors found for {vendor.company_name}")
        
        return vendor
    
    def _already_has_naics(self, vendor: VendorRecord) -> bool:
        return bool(vendor.filtering_metadata.get("naics_codes"))
    
    def _normalize_name(self, name: str) -> str:
        if not name:
            return ""
        
        name = name.upper().strip()
        
        if '/' in name:
            parts = name.split('/')
            name = parts[0].strip()
        
        name = self.suffix_pattern.sub('', name).strip()
        
        name = re.sub(r'[^\w\s]', '', name)
        
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _get_tokens(self, name: str) -> set[str]:
        normalized = self._normalize_name(name)
        tokens = set(normalized.split())
        tokens.discard('')
        return tokens
    
    def _find_matching_vendors(self, target_vendor: VendorRecord) -> list[dict]:
        stmt = (
            select(Vendor.id, Vendor.legal_name, Vendor.city, Vendor.source)
            .where(
                Vendor.source == "canada_odbus",
                Vendor.city.ilike(target_vendor.city)
            )
        )
        
        results = self.db_session.execute(stmt).fetchall()
        
        target_normalized = self._normalize_name(target_vendor.company_name)
        target_tokens = self._get_tokens(target_vendor.company_name)
        
        matches = []
        for row in results:
            vendor_id, legal_name, city, source = row
            
            candidate_normalized = self._normalize_name(legal_name)
            
            string_similarity = ratio(target_normalized, candidate_normalized)
            
            candidate_tokens = self._get_tokens(legal_name)
            if target_tokens and candidate_tokens:
                common_tokens = target_tokens & candidate_tokens
                token_similarity = len(common_tokens) / max(len(target_tokens), len(candidate_tokens))
            else:
                token_similarity = 0.0
            
            combined_similarity = max(string_similarity, token_similarity)
            
            if combined_similarity >= self.similarity_threshold:
                matches.append({
                    "vendor_id": vendor_id,
                    "legal_name": legal_name,
                    "city": city,
                    "similarity": combined_similarity,
                    "string_sim": string_similarity,
                    "token_sim": token_similarity
                })
        
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        
        return matches[:self.max_results]
    
    def _extract_naics_codes(self, matching_vendors: list[dict]) -> list[str]:
        vendor_ids = [v["vendor_id"] for v in matching_vendors]
        
        stmt = (
            select(VendorNAICS.naics_code)
            .where(VendorNAICS.vendor_id.in_(vendor_ids))
            .distinct()
        )
        
        results = self.db_session.execute(stmt).fetchall()
        
        return [row[0] for row in results]
