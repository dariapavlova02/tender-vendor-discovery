"""Smart email generator with MX validation and Serper context verification."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Dict
from urllib.parse import urlparse

try:
    import dns.resolver  # type: ignore
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    dns = None  # type: ignore
    logging.warning("dnspython not installed - MX record checks disabled")

from ..models import VendorRecord
from .base import BaseEnrichmentProvider
from .serper_client import SerperClient


@dataclass
class EmailCandidate:
    """Candidate email with validation metadata."""
    email: str
    prefix: str
    confidence: float
    validation_source: str
    context_snippet: Optional[str] = None


class SmartEmailGeneratorProvider(BaseEnrichmentProvider):
    """
    Level 4 enrichment: Generate and validate email candidates.
    
    Strategy:
    1. Extract domain from vendor website
    2. Check MX records (fast rejection for invalid domains)
    3. Generate email candidates: {prefix}@{domain}
    4. For each candidate, search Serper: site:domain.com "email" "Company Name"
    5. Validate context (email + company name appear together)
    6. Return highest-priority validated email
    """
    
    DEFAULT_PREFIXES = ['sales', 'contact', 'info', 'hello', 'inquiry', 'business']
    
    def __init__(
        self,
        serper_client: SerperClient,
        prefixes: Optional[List[str]] = None,
        enable_mx_check: bool = True,
        enable_serper_validation: bool = True,
        max_candidates: int = 3,
        require_company_context: bool = True,
        min_confidence: float = 0.5,
    ) -> None:
        super().__init__(name="smart_email_generator")
        self.serper_client = serper_client
        self.prefixes = prefixes or self.DEFAULT_PREFIXES
        self.enable_mx_check = enable_mx_check
        self.enable_serper_validation = enable_serper_validation
        self.max_candidates = max_candidates
        self.require_company_context = require_company_context
        self.min_confidence = min_confidence
        self.logger = logging.getLogger(__name__)
        
        self._mx_cache: Dict[str, bool] = {}
        
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
    
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        """Synchronous enrichment (delegates to async)."""
        return asyncio.run(self.enrich_async(vendor))
    
    async def enrich_async(self, vendor: VendorRecord) -> VendorRecord:
        """Generate and validate email candidates."""
        if not vendor.website:
            self.logger.debug(f"Vendor {vendor.company_name} has no website, skipping smart email generation")
            return vendor
        
        domain = self._extract_domain(vendor.website)
        if not domain:
            self.logger.debug(f"Could not extract domain from {vendor.website}")
            return vendor
        
        self.logger.info(f"  → Level 4: Smart email generation for {domain}")
        
        if self.enable_mx_check and not await self._check_mx_records(domain):
            self.logger.info(f"  ✗ Level 4: Domain {domain} has no MX records, skipping")
            return vendor
        
        candidates = self._generate_candidates(domain, vendor.company_name)
        self.logger.debug(f"  Generated {len(candidates)} email candidates: {candidates}")
        
        if self.enable_serper_validation:
            validated = await self._validate_candidates_async(vendor, candidates)
            
            if validated:
                best = validated[0]
                vendor.email = best.email
                vendor.filtering_metadata["email_source"] = "smart_generated"
                vendor.filtering_metadata["email_confidence"] = best.confidence
                vendor.filtering_metadata["email_prefix"] = best.prefix
                vendor.filtering_metadata["email_validation"] = best.validation_source
                if best.context_snippet:
                    vendor.filtering_metadata["email_context"] = best.context_snippet
                
                vendor.enrichment_flags.append(self.name)
                self.logger.info(
                    f"  ✓ Level 4: Validated {best.email} (confidence: {best.confidence:.2f}, prefix: {best.prefix})"
                )
            else:
                self.logger.info(f"  ✗ Level 4: No candidates validated for {domain}")
        else:
            if candidates:
                best = candidates[0]
                vendor.email = best
                vendor.filtering_metadata["email_source"] = "smart_generated_unvalidated"
                vendor.filtering_metadata["email_confidence"] = 0.3
                vendor.enrichment_flags.append(self.name)
                self.logger.info(f"  ⚠ Level 4: Using unvalidated {best}")
        
        return vendor
    
    async def _check_mx_records(self, domain: str) -> bool:
        """Check if domain has MX records (cached)."""
        if not DNS_AVAILABLE or dns is None:
            return True
        
        if domain in self._mx_cache:
            return self._mx_cache[domain]
        
        try:
            loop = asyncio.get_event_loop()
            mx_records = await loop.run_in_executor(
                None, dns.resolver.resolve, domain, 'MX'  # type: ignore
            )
            has_mx = len(mx_records) > 0
            self._mx_cache[domain] = has_mx
            if has_mx:
                self.logger.debug(f"  ✓ MX check: {domain} has {len(mx_records)} MX records")
            return has_mx
        except Exception as e:
            if DNS_AVAILABLE and dns is not None:
                import dns.resolver as resolver  # type: ignore
                if isinstance(e, (resolver.NXDOMAIN, resolver.NoAnswer, resolver.NoNameservers)):
                    self.logger.debug(f"  ✗ MX check failed for {domain}: {e}")
                    self._mx_cache[domain] = False
                    return False
            self.logger.warning(f"  ⚠ MX check error for {domain}: {e}")
            return True
    
    def _generate_candidates(self, domain: str, company_name: Optional[str] = None) -> List[str]:
        """Respect the configured prefix priority and candidate budget."""
        return [f"{prefix}@{domain}" for prefix in self.prefixes[:self.max_candidates]]
    
    @staticmethod
    def _extract_company_prefix(company_name: str) -> Optional[str]:
        """Extract company-based email prefix from company name.
        
        Examples:
            "Bennett Group" → "bennett"
            "Mader Group (CANADA)" → "mader"
            "WSP" → "wsp"
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
    
    async def _validate_candidates_async(
        self, 
        vendor: VendorRecord, 
        candidates: List[str]
    ) -> List[EmailCandidate]:
        """Validate candidates via Serper with context checking."""
        validated = []
        domain = self._extract_domain(vendor.website)
        
        company_clean = re.sub(r'\s*\([^)]*\)', '', vendor.company_name).strip()
        
        for email in candidates:
            prefix = email.split('@')[0]
            
            query = f'site:{domain} "{email}"'
            
            try:
                result = await self.serper_client.search_company_async(
                    company_name=vendor.company_name,
                    include_contacts=False,
                    query=query,
                )
                
                if not result.raw_response:
                    continue
                
                organic = result.raw_response.get('organic', [])
                if not organic:
                    continue
                
                for item in organic[:3]:
                    snippet = item.get('snippet', '')
                    title = item.get('title', '')
                    text = f"{title} {snippet}".lower()
                    # Company context alone cannot validate a guessed mailbox.
                    if not re.search(r'(?<![\w.+-])' + re.escape(email.lower()) + r'(?![\w.-])', text):
                        continue
                    
                    confidence = self._calculate_confidence(
                        text, email, company_clean, domain
                    )
                    
                    if confidence >= self.min_confidence:
                        validated.append(EmailCandidate(
                            email=email,
                            prefix=prefix,
                            confidence=confidence,
                            validation_source="serper_context",
                            context_snippet=snippet[:200]
                        ))
                        break
                
            except Exception as e:
                self.logger.debug(f"  Serper validation failed for {email}: {e}")
                continue
        
        prefix_priority = {p: i for i, p in enumerate(self.prefixes)}
        validated.sort(
            key=lambda c: (-c.confidence, prefix_priority.get(c.prefix, 999))
        )
        
        return validated
    
    def _calculate_confidence(
        self, 
        text: str, 
        email: str, 
        company_name: str, 
        domain: str
    ) -> float:
        """Calculate confidence score based on context."""
        confidence = 0.4
        
        company_lower = company_name.lower()
        email_lower = email.lower()
        domain_lower = domain.lower()
        
        if email_lower in text:
            confidence += 0.2
        
        if company_lower in text or self._normalize_name(company_lower) in self._normalize_name(text):
            confidence += 0.3
        
        if domain_lower in text.replace(email_lower, ''):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    @staticmethod
    def _normalize_name(text: str) -> str:
        """Normalize company name for comparison."""
        return re.sub(r'[^a-z0-9]', '', text.lower())
    
    @staticmethod
    def _extract_domain(url: Optional[str]) -> str:
        """Extract domain from URL."""
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""
