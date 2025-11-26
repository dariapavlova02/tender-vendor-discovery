"""Apollo enrichment helper for pulling organization contacts."""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from ..models import ContactInfo, VendorRecord
from .utils import filter_emails_for_vendor

logger = logging.getLogger(__name__)


class ApolloOrganizationEnrichmentProvider:
    """Fetches organization contact data from Apollo and updates a vendor record."""

    ENRICH_ENDPOINT = "https://api.apollo.io/v1/organizations/enrich"

    def __init__(self, api_key: str, *, session: Optional[requests.Session] = None, timeout: int = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        payload = self._build_payload(vendor)
        if not payload:
            logger.warning("Apollo enrichment skipped: vendor %s missing domain/name", vendor.company_name)
            return vendor

        try:
            response = self.session.post(
                self.ENRICH_ENDPOINT,
                headers={
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Apollo enrichment request failed for %s: %s", vendor.company_name, exc)
            return vendor

        if response.status_code >= 400:
            logger.warning(
                "Apollo enrichment returned %s for %s: %s",
                response.status_code,
                vendor.company_name,
                response.text[:120],
            )
            return vendor

        try:
            data = response.json()
        except ValueError:
            logger.warning("Apollo enrichment response was not JSON for %s", vendor.company_name)
            return vendor

        org = data.get("organization") or data
        if not isinstance(org, dict):
            logger.warning("Apollo enrichment payload malformed for %s", vendor.company_name)
            return vendor

        self._apply_org_data(vendor, org)
        return vendor

    def _build_payload(self, vendor: VendorRecord) -> Optional[Dict[str, Any]]:
        domain = self._extract_domain(vendor.website)
        if domain:
            return {"domain": domain}
        if vendor.company_name:
            return {"organization_name": vendor.company_name}
        return None

    @staticmethod
    def _extract_domain(url: Optional[str]) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _apply_org_data(self, vendor: VendorRecord, org: Dict[str, Any]) -> None:
        website = org.get("website_url") or org.get("domain") or org.get("primary_domain")
        if website and not vendor.website:
            vendor.website = self._normalize_website(website)

        emails = self._collect_emails(org)
        filtered_emails = filter_emails_for_vendor(vendor, emails)
        if filtered_emails and (not vendor.email or vendor.email.endswith(".gov")):
            vendor.email = filtered_emails[0]

        phones = self._collect_phones(org)
        if phones and not vendor.phone:
            vendor.phone = phones[0]

        contact = self._extract_primary_contact(org)
        if contact:
            vendor.primary_contact = contact

        vendor.filtering_metadata["apollo_enriched"] = True
        if "apollo_enriched" not in vendor.enrichment_flags:
            vendor.enrichment_flags.append("apollo_enriched")

    @staticmethod
    def _normalize_website(value: str) -> str:
        value = value.strip()
        if not value:
            return value
        if not value.startswith("http"):
            return f"https://{value}"
        return value

    def _collect_emails(self, org: Dict[str, Any]) -> List[str]:
        emails: List[str] = []
        for key in ("email", "primary_email", "contact_email"):
            if isinstance(org.get(key), str):
                emails.append(org[key])
        raw_emails = org.get("emails") or []
        for entry in raw_emails:
            if isinstance(entry, str):
                emails.append(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("email"), str):
                emails.append(entry["email"])
        contacts = org.get("contacts") or []
        for person in contacts:
            email = person.get("email") if isinstance(person, dict) else None
            if email:
                emails.append(email)
        return emails

    def _collect_phones(self, org: Dict[str, Any]) -> List[str]:
        phones: List[str] = []
        for key in ("phone", "primary_phone"):
            if isinstance(org.get(key), str):
                phones.append(org[key])
        raw_phones = org.get("phone_numbers") or []
        for entry in raw_phones:
            if isinstance(entry, str):
                phones.append(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("phone"), str):
                phones.append(entry["phone"])
        contacts = org.get("contacts") or []
        for person in contacts:
            phone = person.get("phone") if isinstance(person, dict) else None
            if phone:
                phones.append(phone)
        return phones

    def _extract_primary_contact(self, org: Dict[str, Any]) -> Optional[ContactInfo]:
        primary_contact = org.get("primary_contact")
        if isinstance(primary_contact, dict):
            return self._contact_from_dict(primary_contact)
        contacts = org.get("contacts")
        if isinstance(contacts, list):
            for entry in contacts:
                if isinstance(entry, dict):
                    contact = self._contact_from_dict(entry)
                    if contact:
                        return contact
        return None

    @staticmethod
    def _contact_from_dict(data: Dict[str, Any]) -> Optional[ContactInfo]:
        name = data.get("name") or data.get("full_name")
        email = data.get("email")
        phone = data.get("phone") or data.get("mobile")
        organization = data.get("organization") or data.get("company_name")
        if not any([name, email, phone, organization]):
            return None
        return ContactInfo(
            name=name,
            email=email,
            phone=phone,
            organization=organization,
        )
