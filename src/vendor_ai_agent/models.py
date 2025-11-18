"""Core data structures shared across pipeline modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# API metadata structures
# ---------------------------------------------------------------------------


@dataclass
class Address:
    street: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


@dataclass
class CodesMetadata:
    naics: List[str] = field(default_factory=list)
    unspsc: List[str] = field(default_factory=list)
    gsin: List[str] = field(default_factory=list)
    classification: Optional[str] = None


@dataclass
class BuyerInfo:
    name: Optional[str] = None
    department: Optional[str] = None
    organization_path: List[str] = field(default_factory=list)
    address: Address = field(default_factory=Address)


@dataclass
class PlaceOfPerformance(Address):
    pass


@dataclass
class DateMetadata:
    posted: Optional[str] = None
    response_deadline: Optional[str] = None
    tender_start: Optional[str] = None
    tender_end: Optional[str] = None


@dataclass
class SetAsideMetadata:
    code: Optional[str] = None
    description: Optional[str] = None


@dataclass
class EstimatedValue:
    amount: Optional[float] = None
    currency: Optional[str] = None


@dataclass
class AwardSupplierLocation(Address):
    pass


@dataclass
class AwardMetadata:
    award_id: Optional[str] = None
    supplier_name: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    date: Optional[str] = None
    supplier_location: AwardSupplierLocation = field(default_factory=AwardSupplierLocation)


@dataclass
class AttachmentMetadata:
    url: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    label: Optional[str] = None
    source: Optional[str] = None


@dataclass
class APIMetadata:
    external_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    codes: CodesMetadata = field(default_factory=CodesMetadata)
    buyer: BuyerInfo = field(default_factory=BuyerInfo)
    place_of_performance: PlaceOfPerformance = field(default_factory=PlaceOfPerformance)
    dates: DateMetadata = field(default_factory=DateMetadata)
    set_aside: SetAsideMetadata = field(default_factory=SetAsideMetadata)
    estimated_value: EstimatedValue = field(default_factory=EstimatedValue)
    trade_agreements: List[str] = field(default_factory=list)
    awards: List[AwardMetadata] = field(default_factory=list)
    attachments: List[AttachmentMetadata] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Document extraction structures
# ---------------------------------------------------------------------------


@dataclass
class TenderSection:
    title: str
    content: str
    source_path: Optional[Path] = None
    section_type: str = "text"
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class DocSections:
    scope_of_work: str = ""
    technical_requirements: str = ""
    mandatory_requirements: str = ""
    vendor_qualifications: str = ""
    evaluation_criteria: str = ""
    location_details: str = ""
    timeline_details: str = ""


@dataclass
class VolumeItem:
    item: str
    quantity: Optional[float] = None
    unit: Optional[str] = None


@dataclass
class RequiredExperience:
    min_years: Optional[int] = None
    required_project_types: List[str] = field(default_factory=list)


@dataclass
class VendorConstraints:
    allowed_jurisdictions: List[str] = field(default_factory=list)
    business_size: Optional[str] = None
    special_status: List[str] = field(default_factory=list)


@dataclass
class PackagingLeadTimes:
    samples: Optional[int] = None
    regular_orders: Optional[int] = None


@dataclass
class PackagingLogistics:
    special_requirements: List[str] = field(default_factory=list)
    lead_times_days: PackagingLeadTimes = field(default_factory=PackagingLeadTimes)


@dataclass
class StructuredDocData:
    project_type: Optional[str] = None
    sector: Optional[str] = None
    location: Address = field(default_factory=Address)
    volumes: List[VolumeItem] = field(default_factory=list)
    technical_keywords: List[str] = field(default_factory=list)
    required_experience: RequiredExperience = field(default_factory=RequiredExperience)
    required_licenses: List[str] = field(default_factory=list)
    required_certifications: List[str] = field(default_factory=list)
    vendor_constraints: VendorConstraints = field(default_factory=VendorConstraints)
    packaging_logistics: PackagingLogistics = field(default_factory=PackagingLogistics)


@dataclass
class DocExtracted:
    sections: DocSections = field(default_factory=DocSections)
    structured: StructuredDocData = field(default_factory=StructuredDocData)


# ---------------------------------------------------------------------------
# Vendor capability profile (LLM output)
# ---------------------------------------------------------------------------


@dataclass
class KeyRequirement:
    requirement_id: str
    type: str
    description: str
    must_have: bool = True


@dataclass
class TargetIndustryCodes:
    naics: List[str] = field(default_factory=list)
    gsin: List[str] = field(default_factory=list)
    unspsc: List[str] = field(default_factory=list)


@dataclass
class VendorCapabilityProfile:
    summary: Optional[str] = None
    key_requirements: List[KeyRequirement] = field(default_factory=list)
    target_industry_codes: TargetIndustryCodes = field(default_factory=TargetIndustryCodes)


# ---------------------------------------------------------------------------
# Aggregate tender profile
# ---------------------------------------------------------------------------


@dataclass
class TenderProfile:
    tender_id: Optional[str]
    country: Optional[str]
    source_system: Optional[str]
    api_metadata: APIMetadata = field(default_factory=APIMetadata)
    doc_extracted: DocExtracted = field(default_factory=DocExtracted)
    vendor_capability_profile: VendorCapabilityProfile = field(default_factory=VendorCapabilityProfile)


# ---------------------------------------------------------------------------
# Vendor related structures
# ---------------------------------------------------------------------------


@dataclass
class VendorRecord:
    company_name: str
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    is_past_winner: bool = False
    enrichment_flags: List[str] = field(default_factory=list)


@dataclass
class VendorMatchResult:
    vendor: VendorRecord
    capability_match_score: float
    rationale: str
    references: List[str] = field(default_factory=list)


@dataclass
class PipelineArtifacts:
    tender_sections: List[TenderSection]
    tender_profile: TenderProfile
    raw_vendors: List[VendorRecord]
    enriched_vendors: List[VendorRecord]
    final_matches: List[VendorMatchResult]
