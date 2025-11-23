from typing import Optional, List
import logging

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from .base import BaseVendorSource
from ..database.models import Vendor, VendorGSIN, VendorUNSPSC
from ..models import TenderProfile, VendorRecord

logger = logging.getLogger(__name__)


class CanadaContractsSource:
    def __init__(self, session: Session):
        self.session = session
        self.source_name = "canada_contracts"
    
    def search_vendors(
        self,
        gsin_codes: Optional[List[str]] = None,
        unspsc_codes: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        province: Optional[str] = None,
        min_contract_value: Optional[float] = None,
        limit: int = 50,
    ) -> List[Vendor]:
        query = select(Vendor).where(Vendor.source == self.source_name)
        
        filters = []
        
        if gsin_codes:
            gsin_filters = self._build_hierarchical_gsin_filters(gsin_codes)
            if gsin_filters:
                filters.append(
                    Vendor.id.in_(
                        select(VendorGSIN.vendor_id).where(or_(*gsin_filters))
                    )
                )
        
        if unspsc_codes:
            unspsc_filters = self._build_hierarchical_unspsc_filters(unspsc_codes)
            if unspsc_filters:
                filters.append(
                    Vendor.id.in_(
                        select(VendorUNSPSC.vendor_id).where(or_(*unspsc_filters))
                    )
                )
        
        if keywords:
            keyword_filters = [
                Vendor.legal_name.ilike(f"%{kw}%") for kw in keywords
            ]
            filters.append(or_(*keyword_filters))
        
        if province:
            filters.append(Vendor.state == province)
        
        if min_contract_value:
            filters.append(Vendor.total_contract_value >= min_contract_value)
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.order_by(
            Vendor.total_contract_value.desc().nullslast(),
            Vendor.contract_count.desc().nullslast(),
        )
        
        query = query.limit(limit)
        
        result = self.session.execute(query)
        vendors = list(result.scalars().all())
        
        logger.info(
            f"Found {len(vendors)} Canadian vendors "
            f"(GSIN: {gsin_codes}, UNSPSC: {unspsc_codes}, Province: {province})"
        )
        
        return vendors
    
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
            Vendor.source == self.source_name
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def get_vendor_statistics(self) -> dict:
        from sqlalchemy import func
        
        total_vendors = self.session.execute(
            select(func.count(Vendor.id)).where(Vendor.source == self.source_name)
        ).scalar()
        
        total_gsin = self.session.execute(
            select(func.count(VendorGSIN.id)).join(Vendor).where(Vendor.source == self.source_name)
        ).scalar()
        
        total_unspsc = self.session.execute(
            select(func.count(VendorUNSPSC.id)).join(Vendor).where(Vendor.source == self.source_name)
        ).scalar()
        
        total_contract_value = self.session.execute(
            select(func.sum(Vendor.total_contract_value)).where(Vendor.source == self.source_name)
        ).scalar() or 0
        
        return {
            "source": self.source_name,
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
        
        gsin_codes = profile.dynamic_context.gsin_codes if profile.dynamic_context else []
        unspsc_codes = profile.dynamic_context.unspsc_codes if profile.dynamic_context else []
        province = profile.dynamic_context.province if profile.dynamic_context else None
        
        if not gsin_codes and not unspsc_codes and not province:
            return False
        
        return True
    
    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        from ..database.connection import get_session
        
        gsin_codes = profile.dynamic_context.gsin_codes if profile.dynamic_context else []
        unspsc_codes = profile.dynamic_context.unspsc_codes if profile.dynamic_context else []
        province = profile.dynamic_context.province if profile.dynamic_context else None
        keywords = profile.dynamic_context.technical_keywords[:5] if profile.dynamic_context else []
        
        with get_session() as session:
            source = CanadaContractsSource(session)
            vendors = source.search_vendors(
                gsin_codes=gsin_codes if gsin_codes else None,
                unspsc_codes=unspsc_codes if unspsc_codes else None,
                keywords=keywords if keywords else None,
                province=province,
                limit=50,
            )
            
            return [self._convert_to_vendor_record(v) for v in vendors]
    
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
            source=self.name,
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
