"""Unit test for sector-aware keyword extraction (no PDF parsing required)."""
import sys
sys.path.insert(0, 'src')

from vendor_ai_agent.modules.document_processing.field_extractor import FieldExtractor
from vendor_ai_agent.models import TenderSection, DocSections

print("=" * 80)
print("UNIT TEST: Sector-Aware Keyword Extraction")
print("=" * 80)

extractor = FieldExtractor()

# Test Case 1: Ammunition tender with ammo keywords in text
print("\n--- TEST 1: Ammunition tender should only extract ammo keywords ---")

ammo_sections = DocSections(
    scope_of_work="Supply of ammunition cartridges including full metal jacket and hollow point rounds with brass case and non-corrosive primer.",
    technical_requirements="All ammunition must meet saami standard specifications for duty ammunition and training ammunition."
)

structured_ammo = extractor.extract(ammo_sections)

print(f"Detected Sector: {structured_ammo.sector}")
print(f"Keywords extracted: {structured_ammo.technical_keywords}")

from vendor_ai_agent.modules.document_processing.keywords import TECHNICAL_KEYWORDS

construction_kw = TECHNICAL_KEYWORDS.get("construction", [])
it_kw = TECHNICAL_KEYWORDS.get("it", [])
ammo_kw = TECHNICAL_KEYWORDS.get("ammo_supply", [])

construction_contamination = [k for k in structured_ammo.technical_keywords if k in construction_kw]
it_contamination = [k for k in structured_ammo.technical_keywords if k in it_kw]
valid_ammo = [k for k in structured_ammo.technical_keywords if k in ammo_kw]

assert structured_ammo.sector == "ammo_supply", f"Expected sector='ammo_supply', got '{structured_ammo.sector}'"
assert len(valid_ammo) > 0, "Expected to find ammo keywords"
assert len(construction_contamination) == 0, f"Found construction contamination: {construction_contamination}"
assert len(it_contamination) == 0, f"Found IT contamination: {it_contamination}"

print(f"✅ Valid ammo keywords: {valid_ammo}")
print(f"✅ No construction contamination")
print(f"✅ No IT contamination")

# Test Case 2: Construction tender should only extract construction keywords
print("\n--- TEST 2: Construction tender should only extract construction keywords ---")

construction_sections = DocSections(
    scope_of_work="Roofing construction project requiring tpo membrane installation with rigid insulation and vapour barrier.",
    technical_requirements="Roof deck must have r-value insulation and proper flashing at all parapet walls."
)

structured_construction = extractor.extract(construction_sections)

print(f"Detected Sector: {structured_construction.sector}")
print(f"Keywords extracted: {structured_construction.technical_keywords}")

ammo_contamination = [k for k in structured_construction.technical_keywords if k in ammo_kw]
it_contamination2 = [k for k in structured_construction.technical_keywords if k in it_kw]
valid_construction = [k for k in structured_construction.technical_keywords if k in construction_kw]

assert structured_construction.sector == "construction", f"Expected sector='construction', got '{structured_construction.sector}'"
assert len(valid_construction) > 0, "Expected to find construction keywords"
assert len(ammo_contamination) == 0, f"Found ammo contamination: {ammo_contamination}"
assert len(it_contamination2) == 0, f"Found IT contamination: {it_contamination2}"

print(f"✅ Valid construction keywords: {valid_construction}")
print(f"✅ No ammo contamination")
print(f"✅ No IT contamination")

# Test Case 3: Unknown sector should return empty keywords
print("\n--- TEST 3: Unknown sector should return empty keywords ---")

unknown_sections = DocSections(
    scope_of_work="Generic professional services for unspecified consulting work.",
    technical_requirements="Standard business requirements apply."
)

structured_unknown = extractor.extract(unknown_sections)

print(f"Detected Sector: {structured_unknown.sector}")
print(f"Keywords extracted: {structured_unknown.technical_keywords}")

assert structured_unknown.sector == "general", f"Expected sector='general', got '{structured_unknown.sector}'"
assert len(structured_unknown.technical_keywords) == 0, f"Expected empty keywords, got {structured_unknown.technical_keywords}"

print(f"✅ Unknown sector returns empty keywords (safe)")

# Test Case 4: Table keywords should also be sector-aware
print("\n--- TEST 4: Table keyword extraction should be sector-aware ---")

ammo_table = TenderSection(
    title="Ammunition Specifications",
    section_type="table",
    content="| Caliber | Type |\n|---------|------|\n| .223 | full metal jacket |\n| 9mm | hollow point |\n| 12 gauge | brass case |",
    metadata={}
)

construction_table = TenderSection(
    title="Construction Materials",
    section_type="table",
    content="| Material | Spec |\n|---------|------|\n| Membrane | tpo membrane |\n| Insulation | rigid insulation |\n| Barrier | vapour barrier |",
    metadata={}
)

# Create sections with tables
ammo_sections_with_table = DocSections(
    scope_of_work="Supply of ammunition cartridges.",
    tables=[ammo_table]
)

construction_sections_with_table = DocSections(
    scope_of_work="Roofing construction project.",
    tables=[construction_table]
)

structured_ammo_table = extractor.extract(ammo_sections_with_table)
structured_construction_table = extractor.extract(construction_sections_with_table)

print(f"\nAmmo table - Sector: {structured_ammo_table.sector}, Keywords: {structured_ammo_table.technical_keywords}")
print(f"Construction table - Sector: {structured_construction_table.sector}, Keywords: {structured_construction_table.technical_keywords}")

# Check ammo table has no construction keywords
ammo_table_construction_contamination = [k for k in structured_ammo_table.technical_keywords if k in construction_kw]
assert len(ammo_table_construction_contamination) == 0, f"Ammo table has construction contamination: {ammo_table_construction_contamination}"

# Check construction table has no ammo keywords
construction_table_ammo_contamination = [k for k in structured_construction_table.technical_keywords if k in ammo_kw]
assert len(construction_table_ammo_contamination) == 0, f"Construction table has ammo contamination: {construction_table_ammo_contamination}"

print(f"✅ Ammo table: no construction contamination")
print(f"✅ Construction table: no ammo contamination")

print("\n" + "=" * 80)
print("✅ ALL TESTS PASSED - Sector-aware keyword matching working correctly!")
print("=" * 80)
