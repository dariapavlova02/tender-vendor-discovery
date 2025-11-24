"""Standalone test for contact extraction without full imports."""
import re
import sys
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ExtractedContacts:
    emails: List[str]
    phones: List[str]
    contact_names: List[str]
    extraction_method: str
    confidence: float
    email_sources: List[str]
    phone_sources: List[str]

# Simple version of ContactExtractor for testing
class ContactExtractorSimple:
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    PHONE_PATTERNS = [
        r'\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}',
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        r'\b\d{3}\.\d{3}\.\d{4}\b',
    ]
    
    SPAM_PATTERNS = [
        'example.com', 'test@', 'noreply@', 'donotreply@',
        'webmaster@', 'abuse@', 'postmaster@', 'admin@',
    ]
    
    def extract(self, text: str) -> ExtractedContacts:
        emails = self._extract_emails(text)
        phones = self._extract_phones(text)
        
        return ExtractedContacts(
            emails=emails[:5],
            phones=phones[:3],
            contact_names=[],
            extraction_method="regex",
            confidence=0.9 if emails and phones else 0.7,
            email_sources=["scraped_regex"] * len(emails[:5]),
            phone_sources=["scraped_regex"] * len(phones[:3])
        )
    
    def _extract_emails(self, text: str) -> List[str]:
        raw_emails = re.findall(self.EMAIL_PATTERN, text, re.IGNORECASE)
        valid = [e for e in raw_emails if not self._is_spam(e)]
        unique = list(dict.fromkeys([e.lower() for e in valid]))
        return self._prioritize_emails(unique)
    
    def _extract_phones(self, text: str) -> List[str]:
        phones = []
        for pattern in self.PHONE_PATTERNS:
            phones.extend(re.findall(pattern, text))
        normalized = [self._normalize_phone(p) for p in phones]
        return list(dict.fromkeys([p for p in normalized if p]))
    
    def _is_spam(self, email: str) -> bool:
        return any(p in email.lower() for p in self.SPAM_PATTERNS)
    
    def _prioritize_emails(self, emails: List[str]) -> List[str]:
        priority = {
            'sales': 10, 'contact': 8, 'business': 7,
            'inquiries': 7, 'hello': 6, 'info': 5, 'support': 3,
        }
        def score(email: str) -> int:
            for keyword, points in priority.items():
                if keyword in email.lower():
                    return points
            return 1
        return sorted(emails, key=score, reverse=True)
    
    def _normalize_phone(self, phone: str) -> Optional[str]:
        digits = re.sub(r'[^\d]', '', phone)
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        return None

# Run tests
def test_email_extraction():
    extractor = ContactExtractorSimple()
    
    text = """
    Contact Us
    For sales inquiries: sales@acmecorp.com
    For support: support@acmecorp.com
    Phone: (555) 123-4567
    """
    
    contacts = extractor.extract(text)
    
    print("Test 1: Email Extraction")
    print(f"  Emails found: {contacts.emails}")
    print(f"  Phones found: {contacts.phones}")
    assert len(contacts.emails) > 0, "Should find emails"
    assert "sales@acmecorp.com" in contacts.emails, "Should find sales email"
    print("  ✅ PASSED")

def test_email_prioritization():
    extractor = ContactExtractorSimple()
    
    text = "contact@acmecorp.com support@acmecorp.com sales@acmecorp.com info@acmecorp.com"
    contacts = extractor.extract(text)
    
    print("\nTest 2: Email Prioritization")
    print(f"  Emails in order: {contacts.emails}")
    assert contacts.emails[0] == "sales@acmecorp.com", f"Expected sales@ first, got {contacts.emails[0]}"
    print("  ✅ PASSED")

def test_spam_filtering():
    extractor = ContactExtractorSimple()
    
    text = "noreply@acmecorp.com webmaster@acmecorp.com real@acmecorp.com test@example.com"
    contacts = extractor.extract(text)
    
    print("\nTest 3: Spam Filtering")
    print(f"  Valid emails: {contacts.emails}")
    assert "noreply@acmecorp.com" not in contacts.emails, "Should filter noreply"
    assert "webmaster@acmecorp.com" not in contacts.emails, "Should filter webmaster"
    assert "test@example.com" not in contacts.emails, "Should filter example.com"
    assert "real@acmecorp.com" in contacts.emails, "Should keep real email"
    print("  ✅ PASSED")

def test_phone_normalization():
    extractor = ContactExtractorSimple()
    
    text = "(555) 123-4567 555-987-6543 555.111.2222"
    contacts = extractor.extract(text)
    
    print("\nTest 4: Phone Normalization")
    print(f"  Normalized phones: {contacts.phones}")
    for phone in contacts.phones:
        assert phone.startswith("+1"), f"Phone should start with +1: {phone}"
        assert len(phone) == 12, f"Phone should be 12 chars: {phone}"
    print("  ✅ PASSED")

def test_confidence_scoring():
    extractor = ContactExtractorSimple()
    
    text1 = "sales@acmecorp.com phone: 555-123-4567"
    contacts1 = extractor.extract(text1)
    
    text2 = "sales@acmecorp.com"
    contacts2 = extractor.extract(text2)
    
    print("\nTest 5: Confidence Scoring")
    print(f"  With email+phone: {contacts1.confidence}")
    print(f"  With email only: {contacts2.confidence}")
    assert contacts1.confidence == 0.9, "Should be high confidence with both"
    assert contacts2.confidence == 0.7, "Should be medium confidence with one"
    print("  ✅ PASSED")

if __name__ == "__main__":
    print("="*60)
    print("Contact Extraction Tests")
    print("="*60)
    
    try:
        test_email_extraction()
        test_email_prioritization()
        test_spam_filtering()
        test_phone_normalization()
        test_confidence_scoring()
        
        print("\n" + "="*60)
        print("✅✅✅ ALL TESTS PASSED! ✅✅✅")
        print("="*60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
