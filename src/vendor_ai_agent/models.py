"""Core data structures shared across pipeline modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocSections:
    scope_of_work: str = ""
    technical_requirements: str = ""
    mandatory_requirements: str = ""
    vendor_qualifications: str = ""
    evaluation_criteria: str = ""
    location_details: str = ""
    timeline_details: str = ""
    tables: List[TenderSection] = field(default_factory=list)
    table_summaries: str = ""


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
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None


@dataclass
class MandatoryRequirements:
    form_of_offer: bool = False
    jurisdiction_attestation: bool = False
    manufacturer_letter: bool = False
    saami_compliance: bool = False
    mds_required: bool = False
    specs_upload: bool = False
    max_bids_per_item: Optional[int] = None
    other_requirements: List[str] = field(default_factory=list)


@dataclass
class SampleRequirements:
    delivery_days: Optional[int] = None
    lot_numbers: Optional[int] = None
    max_cost_percent: Optional[int] = None
    quantities: Dict[str, int] = field(default_factory=dict)


@dataclass
class EvaluationStage:
    stage_number: int
    name: str
    description: str
    pass_fail: bool = False


@dataclass
class EvaluationCriteria:
    stages: List[EvaluationStage] = field(default_factory=list)
    category_a_weights: Dict[str, float] = field(default_factory=dict)
    category_b_weights: Dict[str, float] = field(default_factory=dict)
    sample_requirements: SampleRequirements = field(default_factory=SampleRequirements)


@dataclass
class ContractTerms:
    start_date: Optional[str] = None
    term_years: Optional[int] = None
    extension_years: Optional[int] = None
    bid_irrevocable_days: Optional[int] = None
    insurance_required: bool = False
    security_clearance_required: bool = False
    wsia_required: bool = False
    tax_compliance_required: bool = False


@dataclass
class Clarification:
    question: str
    answer: str
    addendum_number: Optional[int] = None
    question_number: Optional[str] = None


@dataclass
class Amendment:
    amendment_number: int
    addendum_number: int
    section_changed: str
    change_type: str
    description: str


@dataclass
class StructuredDocData:
    project_type: Optional[str] = None
    sector: Optional[str] = None
    location: Address = field(default_factory=Address)
    solicitation_number: Optional[str] = None
    reference_number: Optional[str] = None
    external_ids: Dict[str, str] = field(default_factory=dict)
    contact_info: ContactInfo = field(default_factory=ContactInfo)
    volumes: List[VolumeItem] = field(default_factory=list)
    technical_keywords: List[str] = field(default_factory=list)
    required_experience: RequiredExperience = field(default_factory=RequiredExperience)
    required_licenses: List[str] = field(default_factory=list)
    required_certifications: List[str] = field(default_factory=list)
    vendor_constraints: VendorConstraints = field(default_factory=VendorConstraints)
    packaging_logistics: PackagingLogistics = field(default_factory=PackagingLogistics)
    mandatory_requirements: MandatoryRequirements = field(default_factory=MandatoryRequirements)
    evaluation_criteria: EvaluationCriteria = field(default_factory=EvaluationCriteria)
    contract_terms: ContractTerms = field(default_factory=ContractTerms)
    clarifications: List[Clarification] = field(default_factory=list)
    amendments: List[Amendment] = field(default_factory=list)


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
class DynamicTenderContext:
    sector: str = "Unknown"
    industry_description: str = ""
    technical_keywords: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)


@dataclass
class TenderProfile:
    tender_id: Optional[str] = None
    country: Optional[str] = None
    source_system: Optional[str] = None
    api_metadata: APIMetadata = field(default_factory=APIMetadata)
    doc_extracted: DocExtracted = field(default_factory=DocExtracted)
    vendor_capability_profile: VendorCapabilityProfile = field(default_factory=VendorCapabilityProfile)
    dynamic_context: DynamicTenderContext = field(default_factory=DynamicTenderContext)


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
