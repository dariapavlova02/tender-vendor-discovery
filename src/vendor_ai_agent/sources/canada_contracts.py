from typing import Optional, List
import logging
import re

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from .base import BaseVendorSource
from ..database.models import Vendor, VendorGSIN, VendorUNSPSC
from ..models import TenderProfile, VendorRecord

logger = logging.getLogger(__name__)


class CanadaContractsSource:
    def __init__(self, session: Session):
        self.session = session
        self.canada_sources = [
            "canada_contracts",
            "canada_odbus",
            "canada_award_notices",
            "canada_pspc_payments",
            "canada_sosa"
        ]
    
    @staticmethod
    def is_technical_term(keyword: str) -> bool:
        if re.match(r'^[.\d].*\d', keyword):
            return True
        if re.match(r'^\d+\.?\d*\s*(mm|cal|gauge)\b', keyword.lower()):
            return True
        return False
    
    @staticmethod
    def expand_keywords_smart(keywords: List[str]) -> List[str]:
        expanded = []
        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue
            
            if CanadaContractsSource.is_technical_term(kw):
                expanded.append(kw)
            else:
                words = kw.split()
                if len(words) > 1:
                    expanded.extend(words)
                else:
                    expanded.append(kw)
        
        return list(set(expanded))
    
    def search_vendors(
        self,
        gsin_codes: Optional[List[str]] = None,
        unspsc_codes: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        province: Optional[str] = None,
        min_contract_value: Optional[float] = None,
        limit: int = 50,
    ) -> List[Vendor]:
        query = select(Vendor).where(Vendor.source.in_(self.canada_sources))
        
        matching_filters = []
        
        if gsin_codes:
            gsin_filters = self._build_hierarchical_gsin_filters(gsin_codes)
            if gsin_filters:
                matching_filters.append(
                    Vendor.id.in_(
                        select(VendorGSIN.vendor_id).where(or_(*gsin_filters))
                    )
                )
        
        if unspsc_codes:
            unspsc_filters = self._build_hierarchical_unspsc_filters(unspsc_codes)
            if unspsc_filters:
                matching_filters.append(
                    Vendor.id.in_(
                        select(VendorUNSPSC.vendor_id).where(or_(*unspsc_filters))
                    )
                )
        
        if keywords:
            expanded_keywords = self.expand_keywords_smart(keywords)
            
            keyword_filters = [
                Vendor.legal_name.ilike(f"%{kw}%") for kw in expanded_keywords if kw.strip()
            ]
            if keyword_filters:
                matching_filters.append(or_(*keyword_filters))
        
        if matching_filters:
            query = query.where(or_(*matching_filters))
        
        if province:
            province_filters = [Vendor.state == province]
            if len(province) > 2:
                province_abbr = self._get_province_abbreviation(province)
                if province_abbr:
                    province_filters.append(Vendor.state == province_abbr)
            else:
                province_full = self._get_province_full_name(province)
                if province_full:
                    province_filters.append(Vendor.state == province_full)
            query = query.where(or_(*province_filters))
        
        if min_contract_value:
            query = query.where(Vendor.total_contract_value >= min_contract_value)
        
        proven_vendors = []
        registry_vendors = []
        
        contract_query = query.where(Vendor.total_contract_value != None)
        contract_query = contract_query.order_by(
            Vendor.total_contract_value.desc(),
            Vendor.contract_count.desc().nullslast(),
        ).limit(int(limit * 0.7))
        
        result = self.session.execute(contract_query)
        proven_vendors = list(result.scalars().all())
        
        registry_query = query.where(
            Vendor.total_contract_value == None,
            Vendor.source == 'canada_odbus'
        ).order_by(Vendor.legal_name).limit(int(limit * 0.3))
        
        result = self.session.execute(registry_query)
        registry_vendors = list(result.scalars().all())
        
        vendors = proven_vendors + registry_vendors
        
        if len(vendors) < 100:
            logger.info(f"Only {len(vendors)} vendors found. Attempting fallback searches.")
            
            if keywords:
                logger.info(f"Attempting sector-based fallback search with generic keywords.")
                
                sector_keywords = []
                for kw in keywords[:5]:
                    kw_lower = kw.lower()
                    if any(term in kw_lower for term in ["ammunition", "ammo", "munitions", "tactical", "defense", "defence", "military", "weapon", "ballistic", "caliber", "ordnance"]):
                        sector_keywords.extend(["ammunition", "ammo", "munitions", "defense", "defence", "security", "tactical", "military", "ordnance"])
                    elif any(term in kw_lower for term in ["vehicle", "transport", "automotive", "truck", "car"]):
                        sector_keywords.extend(["vehicle", "automotive", "transport", "equipment", "truck"])
                    elif any(term in kw_lower for term in ["uniform", "apparel", "clothing", "textile"]):
                        sector_keywords.extend(["uniform", "apparel", "textile", "clothing", "garment"])
                
                if sector_keywords:
                    sector_keywords = list(set(sector_keywords))
                    sector_query = select(Vendor).where(Vendor.source.in_(self.canada_sources))
                    
                    sector_filters = [Vendor.legal_name.ilike(f"%{kw}%") for kw in sector_keywords]
                    sector_query = sector_query.where(or_(*sector_filters))
                    
                    if province:
                        province_filters = [Vendor.state == province]
                        if len(province) > 2:
                            province_abbr = self._get_province_abbreviation(province)
                            if province_abbr:
                                province_filters.append(Vendor.state == province_abbr)
                        else:
                            province_full = self._get_province_full_name(province)
                            if province_full:
                                province_filters.append(Vendor.state == province_full)
                        sector_query = sector_query.where(or_(*province_filters))
                    
                    sector_query = sector_query.order_by(
                        Vendor.total_contract_value.desc().nullslast(),
                        Vendor.contract_count.desc().nullslast(),
                    ).limit(limit)
                    
                    sector_result = self.session.execute(sector_query)
                    sector_vendors = list(sector_result.scalars().all())
                    
                    vendors.extend([v for v in sector_vendors if v not in vendors])
                    vendors = vendors[:limit]
                    
                    logger.info(f"Sector fallback added {len(sector_vendors)} vendors. Total: {len(vendors)}")
            
            if len(vendors) < 100 and province:
                logger.info(f"Still only {len(vendors)} vendors. Retrying without province restriction.")
                fallback_query = select(Vendor).where(Vendor.source.in_(self.canada_sources))
                
                if matching_filters:
                    fallback_query = fallback_query.where(or_(*matching_filters))
                
                fallback_query = fallback_query.order_by(
                    Vendor.total_contract_value.desc().nullslast(),
                    Vendor.contract_count.desc().nullslast(),
                ).limit(limit)
                
                fallback_result = self.session.execute(fallback_query)
                fallback_vendors = list(fallback_result.scalars().all())
                vendors.extend([v for v in fallback_vendors if v not in vendors])
                vendors = vendors[:limit]
                logger.info(f"Without province filter: found {len(fallback_vendors)} vendors. Total: {len(vendors)}")
        
        logger.info(
            f"Found {len(vendors)} Canadian vendors "
            f"(GSIN: {gsin_codes}, UNSPSC: {unspsc_codes}, Province: {province}, Keywords: {keywords})"
        )
        
        return vendors
    
    def _get_province_abbreviation(self, province_full: str) -> Optional[str]:
        province_map = {
            "Ontario": "ON",
            "Quebec": "QC",
            "Québec": "QC",
            "British Columbia": "BC",
            "Alberta": "AB",
            "Manitoba": "MB",
            "Saskatchewan": "SK",
            "Nova Scotia": "NS",
            "New Brunswick": "NB",
            "Newfoundland and Labrador": "NL",
            "Prince Edward Island": "PE",
            "Northwest Territories": "NT",
            "Yukon": "YT",
            "Nunavut": "NU"
        }
        return province_map.get(province_full)
    
    def _get_province_full_name(self, province_abbr: str) -> Optional[str]:
        abbr_map = {
            "ON": "Ontario",
            "QC": "Quebec",
            "BC": "British Columbia",
            "AB": "Alberta",
            "MB": "Manitoba",
            "SK": "Saskatchewan",
            "NS": "Nova Scotia",
            "NB": "New Brunswick",
            "NL": "Newfoundland and Labrador",
            "PE": "Prince Edward Island",
            "NT": "Northwest Territories",
            "YT": "Yukon",
            "NU": "Nunavut"
        }
        return abbr_map.get(province_abbr.upper())
    
    def _build_hierarchical_gsin_filters(self, gsin_codes: List[str]) -> List:
        filters = []
        
        for code in gsin_codes:
            code_clean = code.strip()
            
            filters.append(VendorGSIN.gsin_code == code_clean)
            
            if len(code_clean) >= 2:
                filters.append(VendorGSIN.gsin_code.like(f"{code_clean[:2]}%"))
            
            if len(code_clean) >= 4:
                filters.append(VendorGSIN.gsin_code.like(f"{code_clean[:4]}%"))
        
        return filters
    
    def _build_hierarchical_unspsc_filters(self, unspsc_codes: List[str]) -> List:
        filters = []
        
        for code in unspsc_codes:
            code_clean = code.strip()
            
            filters.append(VendorUNSPSC.unspsc_code == code_clean)
            
            if len(code_clean) >= 2:
                filters.append(VendorUNSPSC.unspsc_code.like(f"{code_clean[:2]}%"))
            
            if len(code_clean) >= 4:
                filters.append(VendorUNSPSC.unspsc_code.like(f"{code_clean[:4]}%"))
            
            if len(code_clean) >= 6:
                filters.append(VendorUNSPSC.unspsc_code.like(f"{code_clean[:6]}%"))
        
        return filters
    
    def get_vendor_by_id(self, vendor_id: int) -> Optional[Vendor]:
        stmt = select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.source.in_(self.canada_sources)
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def get_vendor_statistics(self) -> dict:
        from sqlalchemy import func
        
        total_vendors = self.session.execute(
            select(func.count(Vendor.id)).where(Vendor.source.in_(self.canada_sources))
        ).scalar()
        
        total_gsin = self.session.execute(
            select(func.count(VendorGSIN.id)).join(Vendor).where(Vendor.source.in_(self.canada_sources))
        ).scalar()
        
        total_unspsc = self.session.execute(
            select(func.count(VendorUNSPSC.id)).join(Vendor).where(Vendor.source.in_(self.canada_sources))
        ).scalar()
        
        total_contract_value = self.session.execute(
            select(func.sum(Vendor.total_contract_value)).where(Vendor.source.in_(self.canada_sources))
        ).scalar() or 0
        
        return {
            "source": "all_canada_sources",
            "total_vendors": total_vendors,
            "total_gsin_codes": total_gsin,
            "total_unspsc_codes": total_unspsc,
            "total_contract_value": float(total_contract_value),
        }


class CanadaContractsVendorSource(BaseVendorSource):
    def __init__(self):
        super().__init__(name="canada_contracts")
    
    def is_compatible(self, profile: TenderProfile) -> bool:
        country = profile.dynamic_context.country if profile.dynamic_context else None
        
        if country == "USA":
            return False
        
        if country == "Canada":
            return True
        
        gsin_codes = profile.dynamic_context.gsin_codes if profile.dynamic_context else []
        unspsc_codes = profile.dynamic_context.unspsc_codes if profile.dynamic_context else []
        province = profile.dynamic_context.province if profile.dynamic_context else None
        
        if gsin_codes or unspsc_codes or province:
            return True
        
        return False
    
    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        from ..database.connection import get_session
        
        gsin_codes = profile.dynamic_context.gsin_codes if profile.dynamic_context else []
        unspsc_codes = profile.dynamic_context.unspsc_codes if profile.dynamic_context else []
        province = profile.dynamic_context.province if profile.dynamic_context else None
        keywords = profile.dynamic_context.technical_keywords[:10] if profile.dynamic_context else []
        
        with get_session() as session:
            source = CanadaContractsSource(session)
            vendors = source.search_vendors(
                gsin_codes=gsin_codes if gsin_codes else None,
                unspsc_codes=unspsc_codes if unspsc_codes else None,
                keywords=keywords if keywords else None,
                province=province,
                limit=500,
            )
            
            if len(vendors) < 100 and keywords:
                logger.info(f"Only {len(vendors)} vendors found. Attempting broader keyword search.")
                sector = profile.dynamic_context.sector if profile.dynamic_context else ""
                generic_keywords = self._extract_generic_keywords(keywords, sector)
                
                if generic_keywords != keywords:
                    logger.info(f"Using generic keywords: {generic_keywords}")
                    broader_vendors = source.search_vendors(
                        gsin_codes=gsin_codes if gsin_codes else None,
                        unspsc_codes=unspsc_codes if unspsc_codes else None,
                        keywords=generic_keywords,
                        province=province,
                        limit=500,
                    )
                    
                    existing_ids = {v.id for v in vendors}
                    for v in broader_vendors:
                        if v.id not in existing_ids:
                            vendors.append(v)
                            existing_ids.add(v.id)
                    
                    logger.info(f"After broader search: {len(vendors)} total vendors")
            
            return [self._convert_to_vendor_record(v) for v in vendors]
    
    def _extract_generic_keywords(self, keywords: List[str], sector: str) -> List[str]:
        generic_map = {
            "ammunition": ["ammunition", "ammo", "munitions", "ordnance", "ballistic"],
            "vehicle": ["vehicle", "automotive", "transport", "equipment"],
            "uniform": ["uniform", "apparel", "textile", "clothing"],
            "defense": ["defense", "defence", "security", "tactical", "military"],
            "technology": ["technology", "software", "hardware", "IT", "computer"],
            "construction": ["construction", "building", "infrastructure"],
            "medical": ["medical", "health", "healthcare", "pharmaceutical"],
        }
        
        sector_lower = sector.lower() if sector else ""
        keywords_lower = [kw.lower() for kw in keywords]
        
        for key, generic_terms in generic_map.items():
            if key in sector_lower or any(key in kw for kw in keywords_lower):
                return generic_terms
        
        return keywords
    
    def _convert_to_vendor_record(self, vendor: Vendor) -> VendorRecord:
        location_parts = []
        if vendor.city:
            location_parts.append(vendor.city)
        if vendor.state:
            location_parts.append(vendor.state)
        if vendor.country:
            location_parts.append(vendor.country)
        
        location = ", ".join(location_parts) if location_parts else None
        
        enrichment_flags = []
        if vendor.total_contract_value and vendor.total_contract_value > 100_000_000:
            enrichment_flags.append("high_value_supplier")
        if vendor.contract_count and vendor.contract_count > 50:
            enrichment_flags.append("frequent_supplier")
        
        primary_contact = None
        if vendor.contacts:
            contact = vendor.contacts[0]
            from vendor_ai_agent.models import ContactInfo
            primary_contact = ContactInfo(
                name=f"{contact.first_name or ''} {contact.last_name or ''}".strip() or None,
                email=contact.email,
                phone=contact.phone,
            )
        
        business_types = []
        if isinstance(vendor.business_types, list):
            business_types = vendor.business_types
        
        return VendorRecord(
            company_name=vendor.legal_name or "Unknown",
            website=vendor.website,
            email=primary_contact.email if primary_contact else None,
            phone=primary_contact.phone if primary_contact else None,
            location=location,
            city=vendor.city,
            state=vendor.state,
            country=vendor.country,
            industry=None,
            source=vendor.source,
            is_past_winner=True,
            enrichment_flags=enrichment_flags,
            uei=vendor.uei,
            duns=vendor.duns,
            cage_code=vendor.cage_code,
            business_types=business_types,
            primary_contact=primary_contact,
            total_contract_value=vendor.total_contract_value,
            contract_count=vendor.contract_count,
        )
