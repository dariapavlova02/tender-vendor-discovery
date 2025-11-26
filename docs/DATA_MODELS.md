# Data Models Reference

This document provides comprehensive documentation for all data structures used in the Vendor AI Agent system.

**Related Documentation:**
- [API Reference](API_REFERENCE.md) - Module APIs and method signatures
- [Database Schema](DATABASE_SCHEMA.md) - Database tables and relationships
- [Configuration](CONFIGURATION.md) - System configuration options

---

## Table of Contents

1. [Overview](#overview)
2. [API Metadata Structures](#api-metadata-structures)
3. [Document Extraction Structures](#document-extraction-structures)
4. [Vendor Capability Structures](#vendor-capability-structures)
5. [Tender Profile](#tender-profile)
6. [Vendor Structures](#vendor-structures)
7. [Pipeline Artifacts](#pipeline-artifacts)
8. [Usage Examples](#usage-examples)

---

## Overview

All data models are defined as Python `@dataclass` structures in `src/vendor_ai_agent/models.py`. These models serve as the data contracts between pipeline stages:

- **API Metadata**: Structured data from external APIs (SAM.gov, Canada CKAN)
- **Document Extraction**: Parsed tender documents (PDFs, Word docs)
- **Vendor Capability**: LLM-generated vendor requirement profiles
- **Tender Profile**: Aggregate tender information from all sources
- **Vendor Structures**: Vendor records and matching results
- **Pipeline Artifacts**: Complete pipeline execution results

### Design Principles

- **Immutability**: Dataclasses with default factories for mutable fields
- **Type Safety**: All fields have explicit type annotations
- **Nullability**: Optional fields use `Optional[T]` typing
- **Defaults**: All fields have sensible defaults (None, empty lists, empty strings)
- **Composition**: Complex structures compose simpler structures

---

## API Metadata Structures

These structures represent data received from external government procurement APIs (SAM.gov, Canada CKAN, etc.).

### Address

Base address structure used throughout the system.

```python
@dataclass
class Address:
    street: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
```

**Fields:**
- `street`: Street address line
- `city`: City name
- `state_province`: State (US) or Province (Canada)
- `postal_code`: ZIP code or postal code
- `country`: Country name or ISO code

**Usage:**
```python
address = Address(
    city="Ottawa",
    state_province="Ontario",
    postal_code="K1A 0A9",
    country="Canada"
)
```

---

### CodesMetadata

Industry classification codes from various taxonomies.

```python
@dataclass
class CodesMetadata:
    naics: List[str] = field(default_factory=list)
    unspsc: List[str] = field(default_factory=list)
    gsin: List[str] = field(default_factory=list)
    classification: Optional[str] = None
```

**Fields:**
- `naics`: North American Industry Classification System codes (6-digit)
- `unspsc`: United Nations Standard Products and Services codes
- `gsin`: Goods and Services Identification Number (Canada-specific)
- `classification`: General classification category

**Example:**
```python
codes = CodesMetadata(
    naics=["336411", "336412"],  # Aircraft manufacturing
    gsin=["N6111", "N6112"],
    classification="Defense Manufacturing"
)
```

**References:**
- Database: `vendor_naics`, `vendor_gsin`, `vendor_unspsc` tables
- API: Used in SAM.gov and Canada CKAN responses

---

### BuyerInfo

Information about the procurement buyer/issuing organization.

```python
@dataclass
class BuyerInfo:
    name: Optional[str] = None
    department: Optional[str] = None
    organization_path: List[str] = field(default_factory=list)
    address: Address = field(default_factory=Address)
```

**Fields:**
- `name`: Buyer organization name
- `department`: Specific department or division
- `organization_path`: Hierarchical organization structure (e.g., ["DHS", "CBP", "Border Patrol"])
- `address`: Buyer's address

**Example:**
```python
buyer = BuyerInfo(
    name="Department of Homeland Security",
    department="U.S. Customs and Border Protection",
    organization_path=["DHS", "CBP"],
    address=Address(city="Washington", state_province="DC", country="USA")
)
```

---

### PlaceOfPerformance

Location where contract work will be performed (inherits from Address).

```python
@dataclass
class PlaceOfPerformance(Address):
    pass
```

**Usage:**
```python
pop = PlaceOfPerformance(
    city="Toronto",
    state_province="Ontario",
    country="Canada"
)
```

---

### DateMetadata

Important dates for procurement lifecycle.

```python
@dataclass
class DateMetadata:
    posted: Optional[str] = None
    response_deadline: Optional[str] = None
    tender_start: Optional[str] = None
    tender_end: Optional[str] = None
```

**Fields:**
- `posted`: Date tender was published
- `response_deadline`: Bid submission deadline
- `tender_start`: Contract start date
- `tender_end`: Contract end date

**Format:** ISO 8601 date strings (`YYYY-MM-DD`)

**Example:**
```python
dates = DateMetadata(
    posted="2024-01-15",
    response_deadline="2024-02-28",
    tender_start="2024-04-01",
    tender_end="2025-03-31"
)
```

---

### SetAsideMetadata

Set-aside program information (small business, 8(a), HUBZone, etc.).

```python
@dataclass
class SetAsideMetadata:
    code: Optional[str] = None
    description: Optional[str] = None
```

**Fields:**
- `code`: Set-aside program code (e.g., "SBA", "8A", "SDVOSB")
- `description`: Human-readable description

**Common Codes:**
- `SBA`: Small Business Set-Aside
- `8A`: 8(a) Business Development
- `SDVOSB`: Service-Disabled Veteran-Owned Small Business
- `WOSB`: Women-Owned Small Business
- `HUBZone`: Historically Underutilized Business Zone

**Example:**
```python
set_aside = SetAsideMetadata(
    code="8A",
    description="8(a) Business Development Program"
)
```

**References:**
- Config: `FilteringConfig.set_aside_types`
- Module: `EligibilityChecker` uses this for filtering

---

### EstimatedValue

Contract estimated value with currency.

```python
@dataclass
class EstimatedValue:
    amount: Optional[float] = None
    currency: Optional[str] = None
```

**Fields:**
- `amount`: Numeric value
- `currency`: Currency code (ISO 4217: USD, CAD, etc.)

**Example:**
```python
value = EstimatedValue(
    amount=5000000.00,
    currency="USD"
)
```

---

### AwardSupplierLocation

Location of awarded supplier (inherits from Address).

```python
@dataclass
class AwardSupplierLocation(Address):
    pass
```

---

### AwardMetadata

Historical award information for past contracts.

```python
@dataclass
class AwardMetadata:
    award_id: Optional[str] = None
    supplier_name: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    date: Optional[str] = None
    supplier_location: AwardSupplierLocation = field(default_factory=AwardSupplierLocation)
```

**Fields:**
- `award_id`: Unique award identifier
- `supplier_name`: Name of winning vendor
- `amount`: Award amount
- `currency`: Currency code
- `date`: Award date (ISO 8601)
- `supplier_location`: Supplier's location

**Usage:**
```python
award = AwardMetadata(
    award_id="47QSMD20D0001",
    supplier_name="Acme Defense Solutions",
    amount=2500000.00,
    currency="USD",
    date="2024-03-15",
    supplier_location=AwardSupplierLocation(
        city="Arlington",
        state_province="VA",
        country="USA"
    )
)
```

**Purpose:** Used to identify past winners and prioritize them in vendor discovery.

---

### AttachmentMetadata

File attachments associated with tender.

```python
@dataclass
class AttachmentMetadata:
    url: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    label: Optional[str] = None
    source: Optional[str] = None
```

**Fields:**
- `url`: Download URL for attachment
- `filename`: Original filename
- `mime_type`: MIME type (e.g., "application/pdf")
- `label`: Human-readable label (e.g., "Technical Specifications")
- `source`: Source system (e.g., "sam_gov", "canada_ckan")

**Example:**
```python
attachment = AttachmentMetadata(
    url="https://sam.gov/api/download/12345",
    filename="technical_specs.pdf",
    mime_type="application/pdf",
    label="Technical Specifications",
    source="sam_gov"
)
```

---

### APIMetadata

Complete API response metadata (top-level container).

```python
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
```

**Fields:**
- `external_id`: External system ID (e.g., solicitation number)
- `title`: Tender title
- `description`: Tender description
- `codes`: Industry classification codes
- `buyer`: Issuing organization
- `place_of_performance`: Where work will be performed
- `dates`: Important dates
- `set_aside`: Set-aside program
- `estimated_value`: Contract value
- `trade_agreements`: Trade agreement codes (e.g., ["NAFTA", "WTO_GPA"])
- `awards`: Historical awards
- `attachments`: File attachments

**Example:**
```python
api_metadata = APIMetadata(
    external_id="W912L224R0001",
    title="Tactical Communication Equipment",
    description="Supply and delivery of secure tactical radios",
    codes=CodesMetadata(naics=["334220"]),
    buyer=BuyerInfo(name="U.S. Army", department="Communications-Electronics Command"),
    place_of_performance=PlaceOfPerformance(city="Fort Bragg", state_province="NC"),
    dates=DateMetadata(posted="2024-01-10", response_deadline="2024-02-20"),
    estimated_value=EstimatedValue(amount=10000000.00, currency="USD")
)
```

**Used By:** `TenderProfile.api_metadata`

---

## Document Extraction Structures

These structures represent data extracted from PDF/Word tender documents via LLM parsing.

### TenderSection

A single section or table extracted from document.

```python
@dataclass
class TenderSection:
    title: str
    content: str
    source_path: Optional[Path] = None
    section_type: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Fields:**
- `title`: Section heading (e.g., "Scope of Work", "Technical Requirements")
- `content`: Raw text or table content
- `source_path`: Path to source document
- `section_type`: "text" or "table"
- `metadata`: Additional section metadata (page numbers, confidence scores, etc.)

**Example:**
```python
section = TenderSection(
    title="Scope of Work",
    content="The contractor shall provide...",
    source_path=Path("/data/tender_123.pdf"),
    section_type="text",
    metadata={"page": 5, "confidence": 0.95}
)
```

**Used By:** `DocumentParser` output, `PipelineArtifacts.tender_sections`

---

### DocSections

Structured sections extracted from tender document.

```python
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
```

**Fields:**
- `scope_of_work`: What needs to be done
- `technical_requirements`: Technical specifications
- `mandatory_requirements`: Must-have requirements
- `vendor_qualifications`: Required vendor experience/certifications
- `evaluation_criteria`: How bids will be evaluated
- `location_details`: Geographic requirements
- `timeline_details`: Project timeline and milestones
- `tables`: Extracted tables (pricing, quantities, etc.)
- `table_summaries`: LLM-generated summaries of tables

**Example:**
```python
sections = DocSections(
    scope_of_work="Supply 10,000 tactical vests meeting NIJ Level III-A standards",
    technical_requirements="Materials: 600D polyester, NIJ certified ballistic panels",
    mandatory_requirements="Vendor must be GSA Schedule holder",
    vendor_qualifications="Minimum 5 years manufacturing tactical equipment"
)
```

**Used By:** `DocExtracted.sections`

---

### VolumeItem

Quantity requirement for specific item.

```python
@dataclass
class VolumeItem:
    item: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
```

**Fields:**
- `item`: Item description
- `quantity`: Numeric quantity
- `unit`: Unit of measure (e.g., "each", "kg", "hours")

**Example:**
```python
volume = VolumeItem(
    item="Tactical Radio AN/PRC-152",
    quantity=500,
    unit="each"
)
```

---

### RequiredExperience

Vendor experience requirements.

```python
@dataclass
class RequiredExperience:
    min_years: Optional[int] = None
    required_project_types: List[str] = field(default_factory=list)
```

**Fields:**
- `min_years`: Minimum years of experience
- `required_project_types`: Types of past projects required

**Example:**
```python
experience = RequiredExperience(
    min_years=5,
    required_project_types=["Defense Manufacturing", "Government Contracts"]
)
```

---

### VendorConstraints

Business eligibility constraints.

```python
@dataclass
class VendorConstraints:
    allowed_jurisdictions: List[str] = field(default_factory=list)
    business_size: Optional[str] = None
    special_status: List[str] = field(default_factory=list)
```

**Fields:**
- `allowed_jurisdictions`: Allowed states/provinces/countries
- `business_size`: "small", "medium", "large"
- `special_status`: Required statuses (e.g., ["8(a)", "SDVOSB"])

**Example:**
```python
constraints = VendorConstraints(
    allowed_jurisdictions=["USA", "Canada", "UK"],
    business_size="small",
    special_status=["8(a)"]
)
```

**Used By:** `EligibilityChecker` for filtering

---

### PackagingLeadTimes

Lead time requirements (in days).

```python
@dataclass
class PackagingLeadTimes:
    samples: Optional[int] = None
    regular_orders: Optional[int] = None
```

**Fields:**
- `samples`: Days to deliver samples
- `regular_orders`: Days for regular production orders

---

### PackagingLogistics

Packaging and logistics requirements.

```python
@dataclass
class PackagingLogistics:
    special_requirements: List[str] = field(default_factory=list)
    lead_times_days: PackagingLeadTimes = field(default_factory=PackagingLeadTimes)
```

**Fields:**
- `special_requirements`: Special handling (e.g., "hazmat", "temperature-controlled")
- `lead_times_days`: Lead time requirements

---

### ContactInfo

Contact information structure.

```python
@dataclass
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
```

**Fields:**
- `name`: Contact person name
- `email`: Email address
- `phone`: Phone number
- `organization`: Organization name

**Example:**
```python
contact = ContactInfo(
    name="John Smith",
    email="john.smith@acmecorp.com",
    phone="+1-555-0100",
    organization="Acme Corporation"
)
```

**Used By:** 
- `VendorRecord.primary_contact`
- `StructuredDocData.contact_info` (tender point of contact)
- Database: `vendor_contacts` table

---

### MandatoryRequirements

Boolean flags for mandatory submission requirements.

```python
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
```

**Fields:**
- `form_of_offer`: Signed offer form required
- `jurisdiction_attestation`: Jurisdiction attestation required
- `manufacturer_letter`: Letter from manufacturer required
- `saami_compliance`: SAAMI compliance required (ammunition)
- `mds_required`: Material Data Sheet required
- `specs_upload`: Specification documents required
- `max_bids_per_item`: Maximum bids allowed per line item
- `other_requirements`: Additional requirements

---

### SampleRequirements

Sample submission requirements.

```python
@dataclass
class SampleRequirements:
    delivery_days: Optional[int] = None
    lot_numbers: Optional[int] = None
    max_cost_percent: Optional[int] = None
    quantities: Dict[str, int] = field(default_factory=dict)
```

**Fields:**
- `delivery_days`: Days to deliver samples
- `lot_numbers`: Number of lot numbers required
- `max_cost_percent`: Maximum sample cost as % of bid
- `quantities`: Sample quantities by item (e.g., {"Item A": 5, "Item B": 10})

---

### EvaluationStage

Single stage in multi-stage evaluation process.

```python
@dataclass
class EvaluationStage:
    stage_number: int
    name: str
    description: str
    pass_fail: bool = False
```

**Fields:**
- `stage_number`: Stage sequence number
- `name`: Stage name (e.g., "Technical Evaluation")
- `description`: Stage description
- `pass_fail`: True if pass/fail, False if scored

**Example:**
```python
stage = EvaluationStage(
    stage_number=1,
    name="Technical Compliance",
    description="Verify all technical specifications are met",
    pass_fail=True
)
```

---

### EvaluationCriteria

Complete evaluation criteria structure.

```python
@dataclass
class EvaluationCriteria:
    stages: List[EvaluationStage] = field(default_factory=list)
    category_a_weights: Dict[str, float] = field(default_factory=dict)
    category_b_weights: Dict[str, float] = field(default_factory=dict)
    sample_requirements: SampleRequirements = field(default_factory=SampleRequirements)
```

**Fields:**
- `stages`: Evaluation stages
- `category_a_weights`: Category A scoring weights (e.g., {"technical": 0.6, "price": 0.4})
- `category_b_weights`: Category B scoring weights
- `sample_requirements`: Sample submission requirements

---

### ContractTerms

Contract terms and conditions.

```python
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
```

**Fields:**
- `start_date`: Contract start date (ISO 8601)
- `term_years`: Base contract term in years
- `extension_years`: Optional extension period
- `bid_irrevocable_days`: Days bid must remain valid
- `insurance_required`: Insurance required
- `security_clearance_required`: Security clearance required
- `wsia_required`: Workplace Safety Insurance Act compliance (Canada)
- `tax_compliance_required`: Tax compliance verification required

---

### Clarification

Q&A from tender clarification process.

```python
@dataclass
class Clarification:
    question: str
    answer: str
    addendum_number: Optional[int] = None
    question_number: Optional[str] = None
```

**Fields:**
- `question`: Question from vendor
- `answer`: Buyer's answer
- `addendum_number`: Associated addendum number
- `question_number`: Question identifier

**Example:**
```python
clarification = Clarification(
    question="Can samples be delivered after submission deadline?",
    answer="No, samples must be received by the deadline.",
    addendum_number=2,
    question_number="Q-15"
)
```

---

### Amendment

Tender amendment/change.

```python
@dataclass
class Amendment:
    amendment_number: int
    addendum_number: int
    section_changed: str
    change_type: str
    description: str
```

**Fields:**
- `amendment_number`: Amendment sequence number
- `addendum_number`: Addendum number
- `section_changed`: Section affected
- `change_type`: Type of change (e.g., "addition", "deletion", "modification")
- `description`: Description of change

**Example:**
```python
amendment = Amendment(
    amendment_number=1,
    addendum_number=3,
    section_changed="Technical Specifications - Section 4.2",
    change_type="modification",
    description="Updated ballistic rating requirement from Level II to Level III-A"
)
```

---

### StructuredDocData

Complete structured data extracted from tender document.

```python
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
    naics_codes: List[str] = field(default_factory=list)
```

**Fields:**
- `project_type`: Type of project (e.g., "Supply and Delivery", "Services")
- `sector`: Industry sector (e.g., "Defense", "Healthcare")
- `location`: Primary location
- `solicitation_number`: Solicitation/RFP number
- `reference_number`: Internal reference number
- `external_ids`: External system IDs (e.g., {"sam_gov": "12345"})
- `contact_info`: Point of contact
- `volumes`: Quantity requirements
- `technical_keywords`: Technical keywords for search
- `required_experience`: Experience requirements
- `required_licenses`: Required business licenses
- `required_certifications`: Required certifications (ISO, CMMI, etc.)
- `vendor_constraints`: Eligibility constraints
- `packaging_logistics`: Logistics requirements
- `mandatory_requirements`: Mandatory submission requirements
- `evaluation_criteria`: Evaluation criteria
- `contract_terms`: Contract terms
- `clarifications`: Q&A from clarifications
- `amendments`: Tender amendments
- `naics_codes`: NAICS codes from document

**Example:**
```python
structured = StructuredDocData(
    project_type="Supply and Delivery",
    sector="Defense",
    location=Address(city="Washington", state_province="DC", country="USA"),
    solicitation_number="W912L224R0001",
    contact_info=ContactInfo(name="Jane Doe", email="jane.doe@army.mil"),
    volumes=[VolumeItem(item="Tactical Vest", quantity=1000, unit="each")],
    technical_keywords=["ballistic protection", "NIJ certified", "tactical"],
    required_certifications=["ISO 9001", "Berry Amendment Compliant"],
    naics_codes=["315990", "339113"]
)
```

**Used By:** `DocExtracted.structured`

---

### DocExtracted

Container for all document extraction results.

```python
@dataclass
class DocExtracted:
    sections: DocSections = field(default_factory=DocSections)
    structured: StructuredDocData = field(default_factory=StructuredDocData)
```

**Fields:**
- `sections`: Raw text sections
- `structured`: Structured extracted data

**Used By:** `TenderProfile.doc_extracted`

---

## Vendor Capability Structures

These structures represent LLM-generated vendor capability profiles.

### KeyRequirement

Single vendor capability requirement.

```python
@dataclass
class KeyRequirement:
    requirement_id: str
    type: str
    description: str
    must_have: bool = True
```

**Fields:**
- `requirement_id`: Unique requirement identifier
- `type`: Requirement type (e.g., "technical", "certification", "experience")
- `description`: Human-readable description
- `must_have`: True if mandatory, False if preferred

**Example:**
```python
requirement = KeyRequirement(
    requirement_id="REQ-001",
    type="certification",
    description="NIJ Level III-A ballistic certification",
    must_have=True
)
```

---

### TargetIndustryCodes

Target industry codes for vendor search.

```python
@dataclass
class TargetIndustryCodes:
    naics: List[str] = field(default_factory=list)
    gsin: List[str] = field(default_factory=list)
    unspsc: List[str] = field(default_factory=list)
```

**Fields:**
- `naics`: Target NAICS codes
- `gsin`: Target GSIN codes (Canada)
- `unspsc`: Target UNSPSC codes

**Example:**
```python
codes = TargetIndustryCodes(
    naics=["315990", "339113"],  # Apparel accessories, surgical supplies
    gsin=["N9110"],
    unspsc=["46181501"]
)
```

---

### VendorCapabilityProfile

Complete vendor capability profile (LLM output).

```python
@dataclass
class VendorCapabilityProfile:
    summary: Optional[str] = None
    key_requirements: List[KeyRequirement] = field(default_factory=list)
    target_industry_codes: TargetIndustryCodes = field(default_factory=TargetIndustryCodes)
```

**Fields:**
- `summary`: High-level capability summary
- `key_requirements`: List of key requirements
- `target_industry_codes`: Target industry codes for vendor search

**Example:**
```python
profile = VendorCapabilityProfile(
    summary="Manufacturer of NIJ-certified ballistic protective equipment for law enforcement",
    key_requirements=[
        KeyRequirement(
            requirement_id="REQ-001",
            type="certification",
            description="NIJ Level III-A certification",
            must_have=True
        ),
        KeyRequirement(
            requirement_id="REQ-002",
            type="experience",
            description="5+ years manufacturing tactical equipment",
            must_have=True
        )
    ],
    target_industry_codes=TargetIndustryCodes(naics=["315990", "339113"])
)
```

**Generated By:** `TenderProfiler` (LLM-based)
**Used By:** `CapabilityMatcher` for vendor scoring

---

## Tender Profile

The **TenderProfile** is the central data structure combining all tender information.

### DynamicTenderContext

Dynamic context for vendor search (generated by RequirementExtractor).

```python
@dataclass
class DynamicTenderContext:
    sector: str = "Unknown"
    industry_description: str = ""
    technical_keywords: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)
    gsin_codes: List[str] = field(default_factory=list)
    unspsc_codes: List[str] = field(default_factory=list)
    province: Optional[str] = None
    country: Optional[str] = None
```

**Fields:**
- `sector`: Industry sector
- `industry_description`: Detailed industry description
- `technical_keywords`: Technical search keywords
- `search_terms`: General search terms
- `gsin_codes`: Relevant GSIN codes
- `unspsc_codes`: Relevant UNSPSC codes
- `province`: Target province (Canada)
- `country`: Target country

**Example:**
```python
context = DynamicTenderContext(
    sector="Defense Manufacturing",
    industry_description="Tactical protective equipment for law enforcement",
    technical_keywords=["ballistic", "NIJ certified", "tactical vest"],
    search_terms=["body armor manufacturer", "tactical equipment supplier"],
    gsin_codes=["N9110"],
    province="Ontario",
    country="Canada"
)
```

**Generated By:** `RequirementExtractor`
**Used By:** Vendor discovery sources (Apollo, Serper, SBA DSBS)

---

### TenderProfile

Complete tender profile (top-level aggregate).

```python
@dataclass
class TenderProfile:
    tender_id: Optional[str] = None
    country: Optional[str] = None
    source_system: Optional[str] = None
    api_metadata: APIMetadata = field(default_factory=APIMetadata)
    doc_extracted: DocExtracted = field(default_factory=DocExtracted)
    vendor_capability_profile: VendorCapabilityProfile = field(default_factory=VendorCapabilityProfile)
    dynamic_context: DynamicTenderContext = field(default_factory=DynamicTenderContext)
```

**Fields:**
- `tender_id`: Unique tender identifier
- `country`: Country code (e.g., "USA", "Canada")
- `source_system`: Source system (e.g., "sam_gov", "canada_ckan", "manual_upload")
- `api_metadata`: Data from external API
- `doc_extracted`: Data extracted from documents
- `vendor_capability_profile`: LLM-generated capability profile
- `dynamic_context`: Dynamic search context

**Example:**
```python
profile = TenderProfile(
    tender_id="W912L224R0001",
    country="USA",
    source_system="sam_gov",
    api_metadata=APIMetadata(...),
    doc_extracted=DocExtracted(...),
    vendor_capability_profile=VendorCapabilityProfile(...),
    dynamic_context=DynamicTenderContext(...)
)
```

**Generated By:** `VendorDiscoveryPipeline` (aggregates data from multiple stages)
**Stored In:** `PipelineArtifacts.tender_profile`

---

## Vendor Structures

These structures represent vendor data and matching results.

### VendorRecord

Main vendor data structure.

```python
@dataclass
class VendorRecord:
    company_name: str
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    is_past_winner: bool = False
    enrichment_flags: List[str] = field(default_factory=list)
    uei: Optional[str] = None
    duns: Optional[str] = None
    cage_code: Optional[str] = None
    business_types: List[str] = field(default_factory=list)
    primary_contact: Optional[ContactInfo] = None
    geo_score: float = 0.0
    preliminary_score: float = 0.0
    filtering_metadata: Dict[str, Any] = field(default_factory=dict)
    total_contract_value: Optional[float] = None
    contract_count: Optional[int] = None
```

**Fields:**

**Basic Information:**
- `company_name`: Company legal name (required)
- `website`: Company website URL
- `email`: General company email
- `phone`: Company phone number

**Location:**
- `location`: Full location string (e.g., "San Francisco, CA, USA")
- `city`: City name
- `state`: State/Province
- `country`: Country

**Business Details:**
- `industry`: Industry description
- `source`: Discovery source (e.g., "sam_entity", "apollo", "serper", "canada_ckan")
- `is_past_winner`: True if vendor won similar past contracts

**Government Identifiers:**
- `uei`: Unique Entity Identifier (SAM.gov)
- `duns`: DUNS number
- `cage_code`: Commercial and Government Entity code
- `business_types`: Business type codes (e.g., ["8A", "SDVOSB", "Small Business"])

**Enrichment & Scoring:**
- `enrichment_flags`: Enrichment status flags (e.g., ["apollo_enriched", "contact_scraped"])
- `primary_contact`: Primary contact person
- `geo_score`: Geographic proximity score (0.0-1.0)
- `preliminary_score`: Preliminary match score (0.0-1.0)
- `filtering_metadata`: Metadata from filtering stages

**Contract History:**
- `total_contract_value`: Total value of past contracts
- `contract_count`: Number of past contracts

**Example:**
```python
vendor = VendorRecord(
    company_name="Acme Defense Solutions",
    website="https://acmedefense.com",
    email="info@acmedefense.com",
    city="Arlington",
    state="VA",
    country="USA",
    industry="Defense Manufacturing",
    source="sam_entity",
    is_past_winner=True,
    uei="ABC123DEF456",
    cage_code="1A2B3",
    business_types=["Small Business", "8(a)"],
    primary_contact=ContactInfo(
        name="John Smith",
        email="john.smith@acmedefense.com"
    ),
    geo_score=0.95,
    total_contract_value=25000000.00,
    contract_count=12
)
```

**Database Mapping:** Maps to `vendors` table (see [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md))

---

### VendorMatchResult

Vendor with capability match score and rationale.

```python
@dataclass
class VendorMatchResult:
    vendor: VendorRecord
    capability_match_score: float
    rationale: str
    references: List[str] = field(default_factory=list)
```

**Fields:**
- `vendor`: Vendor record
- `capability_match_score`: LLM-generated capability match score (0.0-1.0)
- `rationale`: Human-readable explanation of score
- `references`: Data sources used for scoring

**Example:**
```python
match = VendorMatchResult(
    vendor=vendor,
    capability_match_score=0.92,
    rationale="Strong match: NIJ Level III-A certified, 8 years experience manufacturing tactical equipment for DOD, 15 past similar contracts. Located in Virginia (excellent geographic match).",
    references=["company_website", "sam_gov_profile", "past_awards"]
)
```

**Generated By:** `CapabilityMatcher`
**Stored In:** `PipelineArtifacts.final_matches`, `PipelineArtifacts.all_matches`

---

### FilteringMetrics

Metrics from vendor filtering process.

```python
@dataclass
class FilteringMetrics:
    total_input: int = 0
    duplicates_removed: int = 0
    geo_filtered: int = 0
    eligibility_filtered: int = 0
    final_count: int = 0
    local_vendors: int = 0
    national_vendors: int = 0
    filter_reasons: Dict[str, int] = field(default_factory=dict)
```

**Fields:**
- `total_input`: Total vendors before filtering
- `duplicates_removed`: Vendors removed as duplicates
- `geo_filtered`: Vendors removed for geographic mismatch
- `eligibility_filtered`: Vendors removed for eligibility issues
- `final_count`: Final vendor count after filtering
- `local_vendors`: Local vendors (within jurisdiction)
- `national_vendors`: National vendors
- `filter_reasons`: Detailed filter reasons (e.g., {"no_website": 5, "wrong_state": 12})

**Example:**
```python
metrics = FilteringMetrics(
    total_input=500,
    duplicates_removed=50,
    geo_filtered=120,
    eligibility_filtered=30,
    final_count=300,
    local_vendors=250,
    national_vendors=50,
    filter_reasons={
        "duplicate_uei": 30,
        "duplicate_website": 20,
        "outside_jurisdiction": 120,
        "missing_set_aside": 30
    }
)
```

**Used By:** `PipelineArtifacts.filtering_metrics`

---

## Pipeline Artifacts

Complete results from pipeline execution.

### PipelineArtifacts

```python
@dataclass
class PipelineArtifacts:
    tender_sections: List[TenderSection]
    tender_profile: TenderProfile
    raw_vendors: List[VendorRecord]
    enriched_vendors: List[VendorRecord]
    final_matches: List[VendorMatchResult]
    all_matches: List[VendorMatchResult] = field(default_factory=list)
    filtered_vendors: List[VendorRecord] = field(default_factory=list)
    filtering_metrics: Optional[FilteringMetrics] = None
    batch_id: int = 1
    processed_batches: List[int] = field(default_factory=list)
```

**Fields:**

**Required (Pipeline Stages 1-7):**
- `tender_sections`: Parsed document sections (Stage 1: DocumentParser)
- `tender_profile`: Complete tender profile (Stage 2: RequirementExtractor + TenderProfiler)
- `raw_vendors`: Discovered vendors (Stage 3: VendorDiscoveryOrchestrator)
- `enriched_vendors`: Enriched vendors (Stage 5: VendorEnricher)
- `final_matches`: Top-N scored matches (Stage 6: CapabilityMatcher)

**Optional (Intermediate Results):**
- `all_matches`: All scored vendors (before top-N selection)
- `filtered_vendors`: Vendors after filtering (Stage 4: DuplicateDetector, EligibilityChecker, GeographicMatcher)
- `filtering_metrics`: Filtering metrics

**Batch Processing:**
- `batch_id`: Current batch number
- `processed_batches`: List of processed batch IDs

**Example:**
```python
artifacts = PipelineArtifacts(
    tender_sections=[...],  # 12 sections
    tender_profile=TenderProfile(...),
    raw_vendors=[...],  # 500 vendors
    enriched_vendors=[...],  # 300 vendors (after filtering and enrichment)
    final_matches=[...],  # Top 25 matches
    filtering_metrics=FilteringMetrics(total_input=500, final_count=300),
    batch_id=1
)
```

**Generated By:** `VendorDiscoveryPipeline.execute()`
**Output To:** JSON/CSV/XLSX files via `OutputGenerator`

---

## Usage Examples

### Example 1: Creating a TenderProfile from API Data

```python
from vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata, DateMetadata

tender = TenderProfile(
    tender_id="W912L224R0001",
    country="USA",
    source_system="sam_gov",
    api_metadata=APIMetadata(
        external_id="W912L224R0001",
        title="Tactical Communication Equipment",
        codes=CodesMetadata(naics=["334220"]),
        dates=DateMetadata(
            posted="2024-01-15",
            response_deadline="2024-02-28"
        )
    )
)
```

### Example 2: Building a VendorRecord

```python
from vendor_ai_agent.models import VendorRecord, ContactInfo

vendor = VendorRecord(
    company_name="Acme Defense Solutions",
    website="https://acmedefense.com",
    city="Arlington",
    state="VA",
    country="USA",
    source="sam_entity",
    uei="ABC123DEF456",
    business_types=["Small Business", "8(a)"],
    primary_contact=ContactInfo(
        name="John Smith",
        email="john.smith@acmedefense.com",
        phone="+1-555-0100"
    )
)
```

### Example 3: Accessing Pipeline Results

```python
from vendor_ai_agent.pipeline import VendorDiscoveryPipeline

pipeline = VendorDiscoveryPipeline(config=config)
artifacts = pipeline.execute(
    source_path="/path/to/tender.pdf",
    tender_id="W912L224R0001"
)

print(f"Total vendors discovered: {len(artifacts.raw_vendors)}")
print(f"Vendors after filtering: {len(artifacts.enriched_vendors)}")
print(f"Top matches: {len(artifacts.final_matches)}")

for match in artifacts.final_matches[:5]:
    print(f"- {match.vendor.company_name}: {match.capability_match_score:.2f}")
    print(f"  Rationale: {match.rationale}")
```

### Example 4: Extracting Structured Data from Documents

```python
from vendor_ai_agent.modules import RequirementExtractor
from vendor_ai_agent.models import TenderSection

sections = [
    TenderSection(
        title="Scope of Work",
        content="Supply 10,000 tactical vests...",
        section_type="text"
    )
]

extractor = RequirementExtractor(llm_config=llm_config)
extracted = extractor.extract(sections)

print(f"Project Type: {extracted.structured.project_type}")
print(f"Sector: {extracted.structured.sector}")
print(f"Technical Keywords: {extracted.structured.technical_keywords}")
print(f"NAICS Codes: {extracted.structured.naics_codes}")
```

### Example 5: Working with FilteringMetrics

```python
metrics = artifacts.filtering_metrics

print(f"Input: {metrics.total_input} vendors")
print(f"Duplicates removed: {metrics.duplicates_removed}")
print(f"Geographic filtering: {metrics.geo_filtered}")
print(f"Eligibility filtering: {metrics.eligibility_filtered}")
print(f"Final: {metrics.final_count} vendors")
print(f"Local: {metrics.local_vendors}, National: {metrics.national_vendors}")

for reason, count in metrics.filter_reasons.items():
    print(f"  - {reason}: {count}")
```

---

## Field Validation & Constraints

### Required Fields

Only `VendorRecord.company_name` is required. All other fields have defaults.

### Type Safety

All fields use explicit type annotations. Use mypy for type checking:

```bash
mypy src/vendor_ai_agent/
```

### Date Formats

All date fields use ISO 8601 format (`YYYY-MM-DD`).

### Score Ranges

- `geo_score`: 0.0 to 1.0
- `preliminary_score`: 0.0 to 1.0  
- `capability_match_score`: 0.0 to 1.0

---

## Related Documentation

- **[API Reference](API_REFERENCE.md)**: Module APIs that use these models
- **[Database Schema](DATABASE_SCHEMA.md)**: Database representation of VendorRecord
- **[Configuration](CONFIGURATION.md)**: System configuration
- **[Pipeline Workflow](PIPELINE_WORKFLOW.md)**: How models flow through pipeline stages

---

## Modification History

| Date | Version | Changes |
|------|---------|---------|
| 2024-11-25 | 1.0.0 | Initial documentation |

---

**Document Status:** ✅ Complete  
**Last Updated:** 2024-11-25  
**Author:** Vendor AI Agent Documentation Team
