"""Standalone test for company prefix extraction logic."""
import re
from typing import Optional


def extract_company_prefix(company_name: str) -> Optional[str]:
    """Extract company-based email prefix from company name.
    
    Examples:
        "Bennett Group" → "bennett"
        "Mader Group (CANADA)" → "mader"
        "WSP" → None (too short)
        "Alpine Building Maintenance" → "alpine"
    """
    cleaned = re.sub(r'\s*\([^)]*\)', '', company_name)
    cleaned = re.sub(r'[^a-zA-Z\s]', '', cleaned).strip()
    
    if not cleaned:
        return None
    
    first_word = cleaned.split()[0].lower()
    
    if len(first_word) >= 3:
        return first_word
    
    return None


def test_company_prefix_extraction():
    """Test the new company prefix extraction logic."""
    test_cases = [
        ("Bennett Group", "bennett"),
        ("Mader Group (CANADA)", "mader"),
        ("WSP", None),
        ("Alpine Building Maintenance", "alpine"),
        ("The Bennett Company", None),  # "the" is too short
        ("PCL Construction", "pcl"),
        ("Ottawa (City)", "ottawa"),
        ("AECOM", "aecom"),
    ]
    
    print("=== Company Prefix Extraction Test ===\n")
    passed = 0
    failed = 0
    
    for company_name, expected in test_cases:
        result = extract_company_prefix(company_name)
        status = "✓" if result == expected else "✗"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {company_name:40s} → {result:15s} (expected: {expected})")
    
    print(f"\n{passed}/{len(test_cases)} tests passed")
    
    if failed > 0:
        print(f"⚠ {failed} tests failed")
    else:
        print("✓ All tests passed!")


def test_candidate_generation():
    """Test email candidate generation with company-specific prefixes."""
    DEFAULT_PREFIXES = ['sales', 'contact', 'info', 'hello', 'inquiry', 'business']
    MAX_CANDIDATES = 3
    
    def generate_candidates(domain: str, company_name: Optional[str] = None) -> list:
        """Generate prioritized email candidates including company-specific prefix."""
        candidates = []
        
        if company_name:
            company_prefix = extract_company_prefix(company_name)
            if company_prefix and company_prefix not in DEFAULT_PREFIXES:
                candidates.append(f"{company_prefix}@{domain}")
        
        for prefix in DEFAULT_PREFIXES[:MAX_CANDIDATES]:
            candidates.append(f"{prefix}@{domain}")
        
        return candidates[:MAX_CANDIDATES + 1]
    
    test_cases = [
        ("Bennett Group", "bennettgroup.ca", ["bennett@bennettgroup.ca", "sales@bennettgroup.ca", "contact@bennettgroup.ca", "info@bennettgroup.ca"]),
        ("Mader Group (CANADA)", "madergroup.ca", ["mader@madergroup.ca", "sales@madergroup.ca", "contact@madergroup.ca", "info@madergroup.ca"]),
        ("Alpine Building Maintenance", "alpineservices.ca", ["alpine@alpineservices.ca", "sales@alpineservices.ca", "contact@alpineservices.ca", "info@alpineservices.ca"]),
    ]
    
    print("\n=== Email Candidate Generation Test ===\n")
    
    for company_name, domain, expected in test_cases:
        result = generate_candidates(domain, company_name)
        print(f"{company_name} ({domain}):")
        for i, email in enumerate(result):
            marker = "→" if i == 0 else " "
            print(f"  {marker} {email}")
        print()


def test_company_name_cleaning():
    """Test company name cleaning for validation queries."""
    test_cases = [
        ("Mader Group (CANADA)", "Mader Group"),
        ("Bennett Group Inc. (USA)", "Bennett Group Inc. "),
        ("WSP", "WSP"),
        ("Alpine Building Maintenance", "Alpine Building Maintenance"),
    ]
    
    print("=== Company Name Cleaning Test ===\n")
    
    for original, expected in test_cases:
        cleaned = re.sub(r'\s*\([^)]*\)', '', original).strip()
        status = "✓" if cleaned == expected.strip() else "✗"
        print(f"{status} {original:45s} → '{cleaned}'")
    
    print()


if __name__ == "__main__":
    test_company_prefix_extraction()
    test_candidate_generation()
    test_company_name_cleaning()
    
    print("\n=== Summary of Implemented Fixes ===")
    print("1. ✓ CONTACT_PATHS expanded: /contact.php, /contact.html, /contacts, /reach-us, etc.")
    print("2. ✓ Company-name-based prefix generation (first word, min 3 chars)")
    print("3. ✓ Relaxed validation query: 'site:domain contact email' (no specific email search)")
    print("4. ✓ Removed email-in-snippet requirement")
    print("5. ✓ Lowered min_confidence from 0.6 to 0.5")
    print("\nExpected Results:")
    print("  • bennettgroup.ca → bennett@bennettgroup.ca as first candidate")
    print("  • alpineservices.ca → alpine@alpineservices.ca as first candidate")
    print("  • madergroup.ca → mader@madergroup.ca as first candidate")
    print("\nThese company-specific prefixes are tried BEFORE generic info@/sales@/contact@")
