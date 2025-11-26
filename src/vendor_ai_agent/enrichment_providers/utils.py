"""Utility helpers for enrichment providers."""
from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import List, Optional

from ..models import VendorRecord

_GOV_SUFFIXES = (".gov", ".gc.ca", ".gouv.qc.ca", ".canada.ca", ".mil")


def _extract_domain(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _domain_root(domain: str) -> str:
    if not domain:
        return ""
    parts = domain.split('.')
    if len(parts) >= 2:
        return parts[-2]
    return domain


def _normalize(text: Optional[str]) -> str:
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


def filter_emails_for_vendor(vendor: VendorRecord, emails: List[str]) -> List[str]:
    """Prefer emails that match vendor domain/company and drop gov inboxes."""
    if not emails:
        return []

    vendor_domain = _extract_domain(vendor.website)
    vendor_root = _domain_root(vendor_domain)
    company_token = _normalize(vendor.company_name)
    vendor_is_gov = bool(
        vendor_domain and any(vendor_domain.endswith(sfx) for sfx in _GOV_SUFFIXES)
    )

    preferred = []
    secondary = []
    fallback = []

    for email in emails:
        dom = email.split('@')[-1].lower().strip()
        dom_clean = dom.replace('-', '').replace('.', '')

        if vendor_domain and dom.endswith(vendor_domain):
            preferred.append(email)
            continue

        if vendor_root and _domain_root(dom) == vendor_root:
            secondary.append(email)
            continue

        if company_token and company_token and company_token in dom_clean:
            secondary.append(email)
            continue

        if any(dom.endswith(sfx) for sfx in _GOV_SUFFIXES):
            if vendor_is_gov:
                fallback.append(email)
            continue

        fallback.append(email)

    return preferred or secondary or fallback
