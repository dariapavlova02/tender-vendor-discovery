"""Contact information extraction from HTML text using regex and LLM fallback."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from .tender_profiler import LLMProvider


@dataclass
class ExtractedContacts:
    """Results of contact extraction."""
    emails: List[str]
    phones: List[str]
    contact_names: List[str]
    extraction_method: str
    confidence: float
    email_sources: List[str]
    phone_sources: List[str]


class ContactExtractor:
    """Extracts email, phone, contact names from HTML text."""
    
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    PHONE_PATTERNS = [
        r'\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}',
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        r'\b\d{3}\.\d{3}\.\d{4}\b',
    ]
    
    NAME_PATTERNS = [
        r'(?:Contact|Manager|Director|VP|President|CEO|Sales|Business\s+Development)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)[\s,]+(?:VP|Director|Manager|President|CEO)',
    ]
    
    SPAM_PATTERNS = [
        'example.com', 'test@', 'noreply@', 'donotreply@',
        'webmaster@', 'abuse@', 'postmaster@', 'admin@',
        'no-reply@', 'bounce@', 'mailer@'
    ]
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider
        self.logger = logging.getLogger(__name__)
    
    def extract(self, text: str, use_llm_fallback: bool = True) -> ExtractedContacts:
        """Extract contacts with regex first, LLM fallback if needed.
        
        Args:
            text: Raw HTML text from contact page
            use_llm_fallback: Use LLM if regex finds nothing
            
        Returns:
            ExtractedContacts with emails, phones, names
        """
        regex_emails = self._extract_emails_regex(text)
        regex_phones = self._extract_phones_regex(text)
        regex_names = self._extract_names_regex(text)
        
        if regex_emails or regex_phones:
            self.logger.debug(
                f"Regex extraction successful: {len(regex_emails)} emails, {len(regex_phones)} phones"
            )
            return ExtractedContacts(
                emails=regex_emails[:5],
                phones=regex_phones[:3],
                contact_names=regex_names[:3],
                extraction_method="regex",
                confidence=0.9 if regex_emails and regex_phones else 0.7,
                email_sources=["scraped_regex"] * len(regex_emails[:5]),
                phone_sources=["scraped_regex"] * len(regex_phones[:3])
            )
        
        if use_llm_fallback and self.llm_provider:
            self.logger.info("Regex found nothing, trying LLM extraction...")
            return self._extract_with_llm(text)
        
        return ExtractedContacts(
            emails=[], phones=[], contact_names=[],
            extraction_method="none", confidence=0.0,
            email_sources=[], phone_sources=[]
        )
    
    def _extract_emails_regex(self, text: str) -> List[str]:
        """Extract and prioritize emails using regex."""
        raw_emails = re.findall(self.EMAIL_PATTERN, text, re.IGNORECASE)
        
        valid_emails = [
            email for email in raw_emails
            if not self._is_spam_email(email)
        ]
        
        unique_emails = list(dict.fromkeys([e.lower() for e in valid_emails]))
        
        return self._prioritize_emails(unique_emails)
    
    def _extract_phones_regex(self, text: str) -> List[str]:
        """Extract and normalize phone numbers using regex."""
        phones = []
        
        for pattern in self.PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            phones.extend(matches)
        
        normalized = [self._normalize_phone(p) for p in phones]
        
        return list(dict.fromkeys([p for p in normalized if p]))
    
    def _extract_names_regex(self, text: str) -> List[str]:
        """Extract contact person names using regex."""
        names = []
        
        for pattern in self.NAME_PATTERNS:
            matches = re.findall(pattern, text)
            names.extend(matches)
        
        cleaned = [self._clean_name(n) for n in names]
        return list(dict.fromkeys([n for n in cleaned if n]))
    
    def _extract_with_llm(self, text: str) -> ExtractedContacts:
        """Use LLM to extract contacts from complex HTML."""
        
        truncated = text[:2000]
        
        prompt = f"""SYSTEM ROLE:
Extract vendor-owned contact channels from the snippet below. Ignore distributor/partner details or third-party references. If nothing valid remains, return empty arrays.

TEXT (trimmed to 2,000 chars):
{truncated}

OUTPUT REQUIREMENTS:
- emails: lowercase company addresses only (same domain as vendor when possible). Exclude noreply/admin/gov domains unless the vendor is a government agency.
- phones: digits only, prefixed with "+" and country code (e.g., +18885551234). Provide up to 3 unique numbers.
- contact_names: keep honorifics/titles ("Dr.", "Capt.") when given; up to 3 names.
- source_hint: label where you found the info (Header, Footer, Body, Sidebar, ContactCard, Unknown).
- notes: short explanation if lists are empty (e.g., "only contact form").
- Keep at most 3 items per list. If nothing survives filtering, return [] and explain in notes.

Return compact JSON ONLY:
{{
  "emails": ["sales@example.com"],
  "phones": ["+18885551234"],
  "contact_names": ["Capt. Jane Doe"],
  "source_hint": "Footer",
  "notes": "direct email listed"
}}"""

        try:
            response = self.llm_provider.generate(prompt, response_format="json")
            
            data = json.loads(response)
            
            emails = data.get("emails", [])
            phones = data.get("phones", [])
            names = data.get("contact_names", [])
            
            self.logger.info(
                f"LLM extraction: {len(emails)} emails, {len(phones)} phones, {len(names)} names"
            )
            
            return ExtractedContacts(
                emails=emails[:5],
                phones=phones[:3],
                contact_names=names[:3],
                extraction_method="llm",
                confidence=0.75 if emails or phones else 0.3,
                email_sources=["scraped_llm"] * len(emails[:5]),
                phone_sources=["scraped_llm"] * len(phones[:3])
            )
        
        except Exception as exc:
            self.logger.warning(f"LLM extraction failed: {exc}")
            return ExtractedContacts(
                emails=[], phones=[], contact_names=[],
                extraction_method="llm_failed", confidence=0.0,
                email_sources=[], phone_sources=[]
            )
    
    def _is_spam_email(self, email: str) -> bool:
        """Check if email is spam/placeholder."""
        email_lower = email.lower()
        return any(pattern in email_lower for pattern in self.SPAM_PATTERNS)
    
    def _prioritize_emails(self, emails: List[str]) -> List[str]:
        """Sort emails by business value (sales > contact > info)."""
        priority = {
            'sales': 10,
            'contact': 8,
            'business': 7,
            'inquiries': 7,
            'hello': 6,
            'info': 5,
            'support': 3,
        }
        
        def score(email: str) -> int:
            for keyword, points in priority.items():
                if keyword in email.lower():
                    return points
            return 1
        
        return sorted(emails, key=score, reverse=True)
    
    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Normalize phone to +1XXXXXXXXXX format."""
        only_digits = re.sub(r'[^\d]', '', phone)
        
        if len(only_digits) == 10:
            return f"+1{only_digits}"
        
        if len(only_digits) == 11 and only_digits.startswith('1'):
            return f"+{only_digits}"
        
        return None
    
    def _clean_name(self, name: str) -> Optional[str]:
        """Clean extracted name."""
        cleaned = ' '.join(name.split())
        
        words = cleaned.split()
        if 2 <= len(words) <= 4:
            return cleaned
        
        return None
