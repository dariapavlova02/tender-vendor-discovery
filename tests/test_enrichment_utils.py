from vendor_ai_agent.enrichment_providers.utils import filter_emails_for_vendor
from vendor_ai_agent.models import VendorRecord


def test_filter_emails_prefers_vendor_domain():
    vendor = VendorRecord(company_name="Honeywell", website="https://www.honeywell.com")
    emails = [
        "glenn.mondoux@tpsgc-pwgsc.gc.ca",
        "contact@honeywell.com",
    ]

    filtered = filter_emails_for_vendor(vendor, emails)

    assert filtered == ["contact@honeywell.com"]


def test_filter_emails_skips_only_government_addresses():
    vendor = VendorRecord(company_name="Honeywell", website="https://www.honeywell.com")
    emails = ["glenn.mondoux@tpsgc-pwgsc.gc.ca"]

    filtered = filter_emails_for_vendor(vendor, emails)

    assert filtered == []


def test_filter_emails_keeps_gov_for_gov_vendor():
    vendor = VendorRecord(company_name="Public Works", website="https://buyandsell.gc.ca")
    emails = ["contact@tpsgc-pwgsc.gc.ca"]

    filtered = filter_emails_for_vendor(vendor, emails)

    assert filtered == ["contact@tpsgc-pwgsc.gc.ca"]
