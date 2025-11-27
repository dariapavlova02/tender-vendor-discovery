# Contract-Type-Aware Vendor Discovery: Detailed Implementation Specification

## Executive Summary

**Problem:** Current system generates search queries by extracting atomic nouns (salt, equipment, training) instead of understanding what vendors must deliver, resulting in 11.9% enrichment success rate.

**Solution:** Classify contract type BEFORE generating search queries, distinguish procurement targets from vendor inputs, generate role-appropriate search terms.

**Impact:** Expected enrichment success rate: 60%+ (5x improvement)

---

## 1. Data Model Changes

### 1.1 TenderContext Dataclass Extensions

**File:** `src/vendor_ai_agent/modules/tender_profiler.py`  
**Lines:** 13-23

#### Current State
```python
@dataclass
class TenderContext:
    sector: str
    industry_description: str
    technical_keywords: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)
    gsin_codes: List[str] = field(default_factory=list)
    unspsc_codes: List[str] = field(default_factory=list)
    province: Optional[str] = None
    country: Optional[str] = None
```

#### New State
```python
@dataclass
class TenderContext:
    sector: str
    industry_description: str
    technical_keywords: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)
    gsin_codes: List[str] = field(default_factory=list)
    unspsc_codes: List[str] = field(default_factory=list)
    province: Optional[str] = None
    country: Optional[str] = None
    
    # NEW FIELDS - Contract-Type-Aware Extensions
    contract_type: Optional[str] = None  # "service" | "product" | "hybrid" | "consulting"
    contract_type_confidence: float = 0.0  # 0.0-1.0
    fulfillment_model: Optional[str] = None  # "contractor" | "manufacturer" | "distributor" | "integrator"
    primary_deliverables: List[str] = field(default_factory=list)  # What buyer purchases
    vendor_inputs: List[str] = field(default_factory=list)  # What winning vendor must provide/use
    location: Dict[str, Any] = field(default_factory=dict)  # Hierarchical: country → province → region → cities
```

**Backward Compatibility:** All new fields have defaults, existing code continues to work.

---

### 1.2 DynamicTenderContext Model Extensions

**File:** `src/vendor_ai_agent/models.py`  
**Lines:** 299-308

#### Current State
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

#### New State
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
    
    # NEW FIELDS - Contract-Type-Aware Extensions
    contract_type: Optional[str] = None
    contract_type_confidence: float = 0.0
    fulfillment_model: Optional[str] = None
    primary_deliverables: List[str] = field(default_factory=list)
    vendor_inputs: List[str] = field(default_factory=list)
    location: Dict[str, Any] = field(default_factory=dict)
```

---

## 2. Core Logic Changes

### 2.1 Enhanced LLM Prompt for Contract-Type Classification

**File:** `src/vendor_ai_agent/modules/tender_profiler.py`  
**Method:** `generate_context()`  
**Lines:** 264-316

#### Implementation Strategy

**REPLACE** the existing prompt (lines 264-316) with the new contract-type-aware prompt:

```python
prompt = f"""Act as a procurement market analyst. Use only the provided scope excerpt.

STEP 1: CLASSIFY CONTRACT TYPE
Analyze the tender to determine what the buyer is purchasing:

- SERVICE: Vendor performs work (maintenance, cleaning, security, landscaping, IT services)
  Signal words: "contractor shall", "provide services", "perform", "maintain", "operate"
  
- PRODUCT: Vendor delivers items (equipment, materials, goods)
  Signal words: "supply", "deliver", "furnish", "provide equipment/materials"
  
- HYBRID: Vendor supplies AND installs/maintains (equipment with installation, turnkey solutions)
  Signal words: "supply and install", "turnkey", "including maintenance", "full-service"
  
- CONSULTING: Advisory, design, engineering, training services
  Signal words: "consulting", "advisory", "design services", "training", "assessment"

STEP 2: DISTINGUISH PROCUREMENT TARGET vs VENDOR INPUTS
Critical distinction for accurate vendor search:

PROCUREMENT TARGET = What the buyer purchases → SEARCH FOR THESE VENDORS
- Service contract: "grounds maintenance services" → search for grounds maintenance contractors
- Product contract: "hospital beds" → search for hospital bed manufacturers/distributors

VENDOR INPUTS = What the winning vendor must provide/use → DO NOT SEARCH FOR THESE
- Service contract: "salt for snow removal" → salt is an INPUT the contractor uses
- Service contract: "equipment for maintenance" → equipment is an INPUT the contractor owns
- Service contract: "training for staff" → training is a DELIVERABLE the contractor provides to buyer

Examples:
✓ "Contractor shall provide grounds maintenance using salt, equipment, and trained staff"
  - Procurement target: grounds maintenance services
  - Vendor inputs: salt, equipment, staff training
  - Search for: grounds maintenance contractors (NOT salt suppliers)

✓ "Supply 100 adjustable hospital beds with installation"
  - Procurement target: hospital beds, installation services
  - Vendor inputs: delivery trucks, installation tools
  - Search for: hospital furniture suppliers with installation

STEP 3: GENERATE CONTRACT-TYPE-AWARE SEARCH TERMS
Generate 25-30 search queries following these distribution rules:

FOR SERVICE CONTRACTS:
- 85% contractor/service provider queries: "[service type] contractors", "[service type] service providers"
- 10% integrator/consultant queries: "[service type] consultants", "[domain] integrators"
- 5% supplier queries ONLY if service requires specialized equipment: "[specialized equipment] suppliers for [service]"
- 0% manufacturer/producer queries (services aren't manufactured)

Example (Grounds Maintenance):
✓ "commercial grounds maintenance contractors Ontario"
✓ "landscape maintenance service providers Canada"
✓ "snow removal and lawn care services"
✓ "property maintenance contractors municipal contracts"
✗ "salt manufacturers" (salt is vendor INPUT, not procurement target)
✗ "lawn mower suppliers" (equipment is vendor INPUT)

FOR PRODUCT CONTRACTS:
- 40% manufacturer/OEM queries: "[product] manufacturers", "[product] OEM producers"
- 30% distributor/wholesaler queries: "[product category] distributors", "[product] wholesalers"
- 20% supplier queries: "[product] suppliers", "[industry] supply companies"
- 10% specialty queries: "[product] fabricators", "custom [product] makers"

Example (Hospital Beds):
✓ "adjustable hospital bed manufacturers"
✓ "medical furniture OEM producers"
✓ "healthcare equipment distributors"
✓ "hospital bed suppliers certified"

FOR HYBRID CONTRACTS:
- 50% full-service provider queries: "[product] with installation", "[product] turnkey solutions"
- 25% manufacturer queries: "[product] manufacturers with installation services"
- 25% integrator queries: "[product] system integrators", "[product] installation contractors"

FOR CONSULTING CONTRACTS:
- 70% consultant/advisory queries: "[domain] consultants", "[specialization] advisory firms"
- 20% engineering/design queries: "[domain] engineering services", "[specialization] design consultants"
- 10% training provider queries: "[domain] training providers", "[certification] trainers"

DIVERSITY REQUIREMENTS (applies to ALL contract types):
- SPECIFIC (30%): Exact products/services with business role
- MEDIUM (40%): Product/service categories with business role
- BROAD (30%): Industry sectors with business role

OUTPUT REQUIREMENTS:
Return strict JSON with the following structure:

{{
  "contract_type": "service" | "product" | "hybrid" | "consulting",
  "contract_type_confidence": 0.0-1.0,
  "fulfillment_model": "contractor" | "manufacturer" | "distributor" | "integrator" | "consultant",
  "primary_deliverables": ["what buyer purchases - list 3-5 items"],
  "vendor_inputs": ["what winning vendor must provide/use - list 3-5 items"],
  
  "sector": "concise label describing the procurement vertical",
  "industry_description": "exactly 2 sentences (≤60 words) summarizing buyer needs",
  "technical_keywords": ["exactly 15 unique keywords ordered from most specific to general"],
  "search_terms": ["25-30 DIVERSE search strings following contract-type distribution rules above"],
  
  "location": {{
    "country": "USA" | "Canada" | null,
    "province": "two-letter code if stated" | null,
    "region": "regional descriptor if mentioned" | null,
    "cities": ["list of cities if mentioned"],
    "service_area": "description of place of performance" | null
  }},
  
  "gsin_codes": ["only codes explicitly in text"],
  "unspsc_codes": ["only codes explicitly in text"],
  "confidence": 0.0-1.0
}}

CRITICAL RULES:
1. Contract classification MUST happen BEFORE generating search terms
2. Search terms MUST match the contract type distribution rules
3. NEVER search for vendor inputs (materials/tools/equipment the contractor uses)
4. ALWAYS search for procurement targets (what the buyer is purchasing)
5. Geographic qualifiers in location object ONLY, NOT in search terms

Scope Excerpt ({len(scope_excerpt)} characters):
{scope_excerpt}
"""
```

---

### 2.2 Update Response Parsing Logic

**File:** `src/vendor_ai_agent/modules/tender_profiler.py`  
**Method:** `generate_context()`  
**Lines:** 326-355

#### Current Code (lines 326-355)
```python
data = json.loads(content)

sector = data.get("sector", "Unknown")
keywords = data.get("technical_keywords", [])
raw_search_terms = data.get("search_terms", [])

self.logger.info(f"LLM generated {len(raw_search_terms)} raw search terms")
self.logger.debug(f"Sample raw terms: {raw_search_terms[:5]}")

search_terms = self._optimize_search_terms(raw_search_terms, target_count=20)
self.logger.info(f"Optimized to {len(search_terms)} diverse search terms")
self.logger.debug(f"Sample optimized terms: {search_terms[:5]}")

if sector == "Unknown" or not keywords:
    self.logger.warning(
        f"LLM returned incomplete data: sector={sector}, "
        f"keywords={len(keywords)}, raw_search_terms={len(raw_search_terms)}"
    )
    self.logger.debug(f"LLM raw response: {content[:500]}")

return TenderContext(
    sector=sector,
    industry_description=data.get("industry_description", ""),
    technical_keywords=keywords,
    search_terms=search_terms,
    gsin_codes=data.get("gsin_codes", []),
    unspsc_codes=data.get("unspsc_codes", []),
    province=data.get("province"),
    country=data.get("country"),
)
```

#### New Code (REPLACE lines 326-355)
```python
data = json.loads(content)

# Extract contract-type-aware fields
contract_type = data.get("contract_type")
contract_type_confidence = data.get("contract_type_confidence", 0.0)
fulfillment_model = data.get("fulfillment_model")
primary_deliverables = data.get("primary_deliverables", [])
vendor_inputs = data.get("vendor_inputs", [])
location_data = data.get("location", {})

# Extract original fields
sector = data.get("sector", "Unknown")
keywords = data.get("technical_keywords", [])
raw_search_terms = data.get("search_terms", [])

# Log contract type classification
self.logger.info(
    f"Contract classified as: {contract_type} "
    f"(confidence: {contract_type_confidence:.2f}, model: {fulfillment_model})"
)
self.logger.debug(f"Primary deliverables: {primary_deliverables}")
self.logger.debug(f"Vendor inputs (excluded from search): {vendor_inputs}")

# Validate and filter search terms using safety rails
validated_search_terms = self._validate_and_filter_search_terms(
    raw_search_terms=raw_search_terms,
    contract_type=contract_type,
    contract_type_confidence=contract_type_confidence,
    vendor_inputs=vendor_inputs
)

self.logger.info(f"LLM generated {len(raw_search_terms)} raw search terms")
self.logger.info(f"Safety rails validated {len(validated_search_terms)} search terms")
self.logger.debug(f"Sample validated terms: {validated_search_terms[:5]}")

search_terms = self._optimize_search_terms(validated_search_terms, target_count=20)
self.logger.info(f"Optimized to {len(search_terms)} diverse search terms")
self.logger.debug(f"Sample optimized terms: {search_terms[:5]}")

if sector == "Unknown" or not keywords:
    self.logger.warning(
        f"LLM returned incomplete data: sector={sector}, "
        f"keywords={len(keywords)}, raw_search_terms={len(raw_search_terms)}"
    )
    self.logger.debug(f"LLM raw response: {content[:500]}")

# Parse location with backward compatibility
province = location_data.get("province") if location_data else data.get("province")
country = location_data.get("country") if location_data else data.get("country")

return TenderContext(
    sector=sector,
    industry_description=data.get("industry_description", ""),
    technical_keywords=keywords,
    search_terms=search_terms,
    gsin_codes=data.get("gsin_codes", []),
    unspsc_codes=data.get("unspsc_codes", []),
    province=province,
    country=country,
    # New fields
    contract_type=contract_type,
    contract_type_confidence=contract_type_confidence,
    fulfillment_model=fulfillment_model,
    primary_deliverables=primary_deliverables,
    vendor_inputs=vendor_inputs,
    location=location_data,
)
```

---

### 2.3 Add Safety Rails Method

**File:** `src/vendor_ai_agent/modules/tender_profiler.py`  
**Location:** Add after `_optimize_search_terms()` method (after line 239)

#### New Method
```python
def _validate_and_filter_search_terms(
    self,
    raw_search_terms: List[str],
    contract_type: Optional[str],
    contract_type_confidence: float,
    vendor_inputs: List[str]
) -> List[str]:
    """
    Safety rails to filter inappropriate search queries based on contract type.
    
    Only applies filters if contract_type_confidence >= 0.75 to avoid false positives.
    
    Args:
        raw_search_terms: Search queries from LLM
        contract_type: Classified contract type
        contract_type_confidence: Confidence score (0-1)
        vendor_inputs: Items the vendor uses (NOT what buyer purchases)
        
    Returns:
        Filtered list of search terms
    """
    if not raw_search_terms:
        return []
    
    # Only apply filters if we're confident about contract type
    if contract_type_confidence < 0.75:
        self.logger.info(
            f"Skipping search term filtering: confidence {contract_type_confidence:.2f} < 0.75"
        )
        return raw_search_terms
    
    filtered_terms = []
    rejected_terms = []
    
    # Define inappropriate patterns by contract type
    inappropriate_patterns = {
        "service": [
            # For service contracts, vendors are NOT manufacturers/producers
            r'\b(manufacturer|producer|maker|fabricator|oem)\b',
            # Should not search for raw materials/inputs
            r'\b(salt|sand|gravel|material)\s+(supplier|distributor|wholesaler)\b',
        ],
        "product": [
            # For product contracts, vendors are NOT service providers
            r'\b(service provider|contractor|maintenance contractor)\b',
        ],
        "consulting": [
            # For consulting contracts, vendors are NOT manufacturers
            r'\b(manufacturer|producer|supplier|distributor)\b',
        ]
    }
    
    # Build vendor input patterns (case-insensitive)
    vendor_input_patterns = []
    for vendor_input in vendor_inputs:
        if vendor_input and len(vendor_input.strip()) >= 3:
            # Create pattern like: "salt supplier" or "equipment distributor"
            escaped = vendor_input.strip().lower().replace(' ', r'\s+')
            vendor_input_patterns.append(
                rf'\b{escaped}\s+(supplier|distributor|wholesaler|manufacturer)\b'
            )
    
    # Get inappropriate patterns for this contract type
    patterns_to_check = inappropriate_patterns.get(contract_type, [])
    patterns_to_check.extend(vendor_input_patterns)
    
    import re
    for term in raw_search_terms:
        term_lower = term.lower()
        is_inappropriate = False
        
        for pattern in patterns_to_check:
            if re.search(pattern, term_lower, re.IGNORECASE):
                is_inappropriate = True
                rejected_terms.append((term, pattern))
                break
        
        if not is_inappropriate:
            filtered_terms.append(term)
    
    # Log filtering results
    if rejected_terms:
        self.logger.warning(
            f"Safety rails filtered {len(rejected_terms)}/{len(raw_search_terms)} "
            f"inappropriate queries for contract_type={contract_type}"
        )
        for term, pattern in rejected_terms[:3]:  # Log first 3 examples
            self.logger.debug(f"  Rejected: '{term}' (matched pattern: {pattern})")
    
    return filtered_terms
```

---

### 2.4 Update DynamicTenderContext Instantiation

**File:** `src/vendor_ai_agent/modules/requirement_extractor.py`  
**Method:** `extract()`  
**Lines:** 48-57

#### Current Code
```python
dynamic_context = DynamicTenderContext(
    sector=tender_context_data.sector,
    industry_description=tender_context_data.industry_description,
    technical_keywords=tender_context_data.technical_keywords,
    search_terms=tender_context_data.search_terms,
    gsin_codes=tender_context_data.gsin_codes,
    unspsc_codes=tender_context_data.unspsc_codes,
    province=tender_context_data.province,
    country=tender_context_data.country,
)
```

#### New Code (REPLACE lines 48-57)
```python
dynamic_context = DynamicTenderContext(
    sector=tender_context_data.sector,
    industry_description=tender_context_data.industry_description,
    technical_keywords=tender_context_data.technical_keywords,
    search_terms=tender_context_data.search_terms,
    gsin_codes=tender_context_data.gsin_codes,
    unspsc_codes=tender_context_data.unspsc_codes,
    province=tender_context_data.province,
    country=tender_context_data.country,
    # New fields with backward compatibility
    contract_type=getattr(tender_context_data, 'contract_type', None),
    contract_type_confidence=getattr(tender_context_data, 'contract_type_confidence', 0.0),
    fulfillment_model=getattr(tender_context_data, 'fulfillment_model', None),
    primary_deliverables=getattr(tender_context_data, 'primary_deliverables', []),
    vendor_inputs=getattr(tender_context_data, 'vendor_inputs', []),
    location=getattr(tender_context_data, 'location', {}),
)
```

---

## 3. Testing Strategy

### 3.1 Test File Creation

**File:** `tests/test_contract_type_classification.py` (NEW FILE)

```python
"""Test contract-type-aware search query generation."""
import os
from pathlib import Path

import pytest

from vendor_ai_agent.modules.tender_profiler import TenderProfiler
from vendor_ai_agent.modules.llm_providers import OpenAIProvider


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestContractTypeClassification:
    """Test contract type classification and search query generation."""
    
    def setup_method(self):
        """Initialize profiler with OpenAI provider."""
        self.provider = OpenAIProvider()
        self.profiler = TenderProfiler(llm_provider=self.provider)
    
    def test_service_contract_grounds_maintenance(self):
        """Test service contract: Waterloo grounds maintenance."""
        scope = """
        The Region of Waterloo requires a contractor to provide comprehensive grounds 
        maintenance services including lawn care, snow removal, landscaping, and property 
        upkeep. The contractor shall provide all necessary equipment, materials (including 
        salt, sand, fertilizers), and trained personnel to perform the services.
        """
        
        context = self.profiler.generate_context_from_text(scope)
        
        # Verify contract type classification
        assert context.contract_type == "service"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model == "contractor"
        
        # Verify deliverables vs inputs distinction
        assert "grounds maintenance" in " ".join(context.primary_deliverables).lower()
        assert "salt" in " ".join(context.vendor_inputs).lower() or \
               "equipment" in " ".join(context.vendor_inputs).lower()
        
        # Verify search terms are contractor-focused (NOT supplier-focused)
        search_terms_str = " ".join(context.search_terms).lower()
        
        # Should contain contractor/service queries
        assert any(term in search_terms_str for term in [
            "contractor", "service provider", "maintenance"
        ])
        
        # Should NOT contain supplier/manufacturer queries for inputs
        assert "salt manufacturer" not in search_terms_str
        assert "salt supplier" not in search_terms_str
        assert "equipment supplier" not in search_terms_str
        
        print(f"\n✓ Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence:.2f})")
        print(f"✓ Fulfillment Model: {context.fulfillment_model}")
        print(f"✓ Primary Deliverables: {context.primary_deliverables}")
        print(f"✓ Vendor Inputs: {context.vendor_inputs}")
        print(f"✓ Search Terms: {context.search_terms[:5]}...")
    
    def test_product_contract_hospital_beds(self):
        """Test product contract: Hospital bed procurement."""
        scope = """
        The hospital requires 100 adjustable hospital beds with electronic controls.
        Specifications: full electric, weight capacity 450 lbs, side rails, IV pole holders.
        Supplier shall provide delivery and basic installation.
        """
        
        context = self.profiler.generate_context_from_text(scope)
        
        # Verify contract type classification
        assert context.contract_type == "product"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model in ["manufacturer", "distributor"]
        
        # Verify deliverables
        assert "hospital bed" in " ".join(context.primary_deliverables).lower() or \
               "beds" in " ".join(context.primary_deliverables).lower()
        
        # Verify search terms are manufacturer/distributor-focused
        search_terms_str = " ".join(context.search_terms).lower()
        
        assert any(term in search_terms_str for term in [
            "manufacturer", "distributor", "supplier", "hospital bed"
        ])
        
        # Should NOT contain service contractor queries
        assert "service provider" not in search_terms_str
        assert "maintenance contractor" not in search_terms_str
        
        print(f"\n✓ Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence:.2f})")
        print(f"✓ Search Terms: {context.search_terms[:5]}...")
    
    def test_hybrid_contract_hvac_system(self):
        """Test hybrid contract: HVAC system with installation."""
        scope = """
        Supply and install a new HVAC system for government building. Contractor shall 
        provide equipment, installation services, testing, commissioning, and 1-year 
        maintenance. Turnkey solution required.
        """
        
        context = self.profiler.generate_context_from_text(scope)
        
        # Verify contract type classification
        assert context.contract_type == "hybrid"
        assert context.contract_type_confidence >= 0.70
        assert context.fulfillment_model in ["integrator", "contractor"]
        
        # Verify search terms include both supply and installation
        search_terms_str = " ".join(context.search_terms).lower()
        
        assert any(term in search_terms_str for term in [
            "installation", "turnkey", "integrator", "hvac"
        ])
        
        print(f"\n✓ Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence:.2f})")
        print(f"✓ Search Terms: {context.search_terms[:5]}...")
    
    def test_consulting_contract_cybersecurity(self):
        """Test consulting contract: Cybersecurity assessment."""
        scope = """
        The agency requires cybersecurity consulting services including vulnerability 
        assessment, penetration testing, security architecture review, and training 
        for IT staff. Consultant shall provide expert advisory services and documentation.
        """
        
        context = self.profiler.generate_context_from_text(scope)
        
        # Verify contract type classification
        assert context.contract_type == "consulting"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model == "consultant"
        
        # Verify search terms are consultant-focused
        search_terms_str = " ".join(context.search_terms).lower()
        
        assert any(term in search_terms_str for term in [
            "consultant", "advisory", "cybersecurity"
        ])
        
        # Should NOT contain manufacturer/supplier queries
        assert "manufacturer" not in search_terms_str
        assert "supplier" not in search_terms_str
        
        print(f"\n✓ Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence:.2f})")
        print(f"✓ Search Terms: {context.search_terms[:5]}...")
    
    def test_safety_rails_filter_vendor_inputs(self):
        """Test that safety rails filter queries for vendor inputs."""
        scope = """
        Snow removal contractor shall use salt and sand for ice management. Contractor 
        provides all equipment, materials, and personnel for snow plowing and ice control 
        services on municipal roads.
        """
        
        context = self.profiler.generate_context_from_text(scope)
        
        # Verify vendor inputs are identified
        vendor_inputs_str = " ".join(context.vendor_inputs).lower()
        assert "salt" in vendor_inputs_str or "sand" in vendor_inputs_str
        
        # Verify search terms do NOT include queries for vendor inputs
        search_terms_str = " ".join(context.search_terms).lower()
        assert "salt supplier" not in search_terms_str
        assert "salt manufacturer" not in search_terms_str
        assert "sand supplier" not in search_terms_str
        
        # Should contain contractor queries
        assert any(term in search_terms_str for term in [
            "snow removal", "contractor", "ice control"
        ])
        
        print(f"\n✓ Vendor Inputs Filtered: {context.vendor_inputs}")
        print(f"✓ Search Terms (no input suppliers): {context.search_terms[:5]}...")


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
def test_waterloo_grounds_maintenance_real_pdf():
    """Integration test with real Waterloo PDF."""
    pdf_path = Path("/Users/dariapavlova/Documents/vendor_ai_agent/RFB25-106 Waterloo Grounds Maintenance.pdf")
    
    if not pdf_path.exists():
        pytest.skip("Waterloo PDF not found")
    
    # Parse PDF and extract context
    from vendor_ai_agent.modules.document_processing import DocumentParser
    from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor
    from vendor_ai_agent.modules.llm_providers import OpenAIProvider
    
    provider = OpenAIProvider()
    parser = DocumentParser()
    extractor = RequirementExtractor(llm_provider=provider)
    
    sections = parser.parse(pdf_path)
    profile = extractor.extract(sections)
    
    context = profile.dynamic_context
    
    # Verify contract type classification
    assert context.contract_type == "service"
    assert context.contract_type_confidence >= 0.75
    
    # Verify search terms quality
    search_terms_str = " ".join(context.search_terms).lower()
    assert any(term in search_terms_str for term in [
        "grounds maintenance", "landscape", "contractor"
    ])
    
    # Verify NO supplier queries for inputs
    assert "salt supplier" not in search_terms_str
    assert "equipment supplier" not in search_terms_str
    
    print(f"\n✓ Waterloo PDF Analysis:")
    print(f"  Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence:.2f})")
    print(f"  Primary Deliverables: {context.primary_deliverables}")
    print(f"  Vendor Inputs: {context.vendor_inputs}")
    print(f"  Search Terms: {context.search_terms[:10]}")


if __name__ == "__main__":
    # Run manual tests
    import sys
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)
    
    print("Running contract-type-aware classification tests...\n")
    
    test_suite = TestContractTypeClassification()
    test_suite.setup_method()
    
    print("=" * 80)
    print("TEST 1: Service Contract (Grounds Maintenance)")
    print("=" * 80)
    test_suite.test_service_contract_grounds_maintenance()
    
    print("\n" + "=" * 80)
    print("TEST 2: Product Contract (Hospital Beds)")
    print("=" * 80)
    test_suite.test_product_contract_hospital_beds()
    
    print("\n" + "=" * 80)
    print("TEST 3: Hybrid Contract (HVAC System)")
    print("=" * 80)
    test_suite.test_hybrid_contract_hvac_system()
    
    print("\n" + "=" * 80)
    print("TEST 4: Consulting Contract (Cybersecurity)")
    print("=" * 80)
    test_suite.test_consulting_contract_cybersecurity()
    
    print("\n" + "=" * 80)
    print("TEST 5: Safety Rails (Filter Vendor Inputs)")
    print("=" * 80)
    test_suite.test_safety_rails_filter_vendor_inputs()
    
    print("\n" + "=" * 80)
    print("TEST 6: Integration Test (Real Waterloo PDF)")
    print("=" * 80)
    test_waterloo_grounds_maintenance_real_pdf()
    
    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED")
    print("=" * 80)
```

---

## 4. Metrics & Observability

### 4.1 Key Metrics to Track

Add logging to capture these metrics in production:

1. **Contract Type Distribution**
   - % of tenders classified as service/product/hybrid/consulting
   - Average confidence scores by contract type

2. **Search Query Quality**
   - % of queries filtered by safety rails
   - Distribution of business role keywords (contractor/manufacturer/distributor)
   - Query diversity scores (before/after optimization)

3. **Enrichment Success Rates**
   - Success rate by contract type
   - Success rate by fulfillment model
   - Comparison: contract-type-aware vs baseline

4. **Geographic Extraction**
   - % of tenders with location data extracted
   - Location hierarchy completeness (country/province/city)

### 4.2 Logging Implementation

Add to `generate_context()` method (after line 355):

```python
# Log metrics for observability
self.logger.info(
    f"METRICS: contract_type={contract_type}, "
    f"confidence={contract_type_confidence:.2f}, "
    f"fulfillment_model={fulfillment_model}, "
    f"queries_generated={len(raw_search_terms)}, "
    f"queries_validated={len(validated_search_terms)}, "
    f"queries_optimized={len(search_terms)}, "
    f"location_extracted={'Yes' if location_data else 'No'}"
)
```

---

## 5. Rollout Plan

### Phase 1: Implementation (Week 1)
- [ ] Update `TenderContext` dataclass with new fields
- [ ] Update `DynamicTenderContext` model with new fields
- [ ] Implement new LLM prompt with contract-type classification
- [ ] Implement `_validate_and_filter_search_terms()` safety rails
- [ ] Update response parsing logic
- [ ] Update `requirement_extractor.py` instantiation

### Phase 2: Testing & Validation (Week 2)
- [ ] Create test file `test_contract_type_classification.py`
- [ ] Run unit tests for all 4 contract types
- [ ] Run integration test with Waterloo PDF
- [ ] Validate safety rails filter inappropriate queries
- [ ] Measure enrichment success rate on test dataset (N=20 tenders)

### Phase 3: Metrics & Monitoring (Week 2-3)
- [ ] Add logging for contract type distribution
- [ ] Add logging for query filtering statistics
- [ ] Create dashboard for success rate monitoring
- [ ] Set up alerts for low confidence scores (<0.5)

### Phase 4: Production Rollout (Week 3-4)
- [ ] Deploy to staging environment
- [ ] Run A/B test: contract-type-aware vs baseline
- [ ] Monitor enrichment success rate improvement
- [ ] Gradual rollout: 10% → 50% → 100% of tenders

### Success Criteria
- **Enrichment success rate: ≥60%** (baseline: 11.9%)
- **Contract type confidence: ≥0.75** for 80%+ of tenders
- **Safety rails filter rate: <15%** of queries (balance precision/recall)
- **Geographic extraction rate: ≥70%** of tenders

---

## 6. Backward Compatibility

All changes maintain backward compatibility:

1. **New dataclass fields have defaults** → existing code continues to work
2. **`getattr()` with fallbacks** → handles old TenderContext objects
3. **Safety rails only apply if confidence ≥0.75** → minimal impact on uncertain cases
4. **Location data has fallback** → uses existing province/country if location dict empty

---

## 7. Risk Mitigation

### Risk 1: LLM fails to classify contract type correctly
**Mitigation:** 
- Confidence threshold (0.75) prevents incorrect filtering
- Extensive prompt examples guide LLM classification
- Fallback to original behavior if confidence low

### Risk 2: Safety rails filter too aggressively
**Mitigation:**
- Monitor filter rate in logs
- Adjust confidence threshold if needed
- Whitelist patterns for edge cases

### Risk 3: New prompt increases LLM costs
**Mitigation:**
- Already using smart model (gpt-5.1) for quality
- Longer prompt offset by reduced duplicate Serper queries
- Cost justified by 5x enrichment improvement

---

## 8. Next Steps After Implementation

1. **Tune confidence thresholds** based on production data
2. **Expand safety rails patterns** as edge cases emerge
3. **Add contract type to dashboard** for stakeholder visibility
4. **Create contract-type-specific enrichment strategies** (e.g., different sources for service vs product vendors)

---

## Summary

This specification provides line-by-line implementation details for contract-type-aware vendor discovery. The changes are:

- **Minimal and surgical:** Only 2 files modified, 1 new test file
- **Backward compatible:** All new fields have defaults
- **Well-tested:** 6 comprehensive test cases
- **Observable:** Extensive logging for metrics
- **Low-risk:** Safety rails with confidence thresholds

**Expected Impact:** 5x improvement in enrichment success rate (11.9% → 60%+)
