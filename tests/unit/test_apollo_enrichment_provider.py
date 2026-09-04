from vendor_ai_agent.enrichment_providers.apollo_contacts import ApolloOrganizationEnrichmentProvider
from vendor_ai_agent.models import VendorRecord


class DummyResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ""

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        return self.response


def test_apollo_enrichment_updates_contacts():
    payload = {
        "organization": {
            "primary_email": "info@example.com",
            "phone_numbers": [{"phone": "+1-202-555-0101"}],
            "contacts": [
                {"name": "Jordan Cole", "email": "jordan@example.com", "phone": "+1-202-555-0199"}
            ],
            "website_url": "example.com",
        }
    }
    session = DummySession(DummyResponse(200, payload))
    provider = ApolloOrganizationEnrichmentProvider("fake-key", session=session)
    vendor = VendorRecord(company_name="Example Co")

    provider.enrich(vendor)

    assert vendor.email == "info@example.com"
    assert vendor.phone == "+1-202-555-0101"
    assert vendor.primary_contact and vendor.primary_contact.name == "Jordan Cole"
    assert vendor.filtering_metadata.get("apollo_enriched") is True
    assert "apollo_enriched" in vendor.enrichment_flags


def test_apollo_payload_falls_back_to_company_name():
    payload = {"organization": {}}
    session = DummySession(DummyResponse(200, payload))
    provider = ApolloOrganizationEnrichmentProvider("fake-key", session=session)
    vendor = VendorRecord(company_name="No Site LLC")

    provider.enrich(vendor)

    sent_payload = session.calls[0]["json"]
    assert sent_payload == {"organization_name": "No Site LLC"}
