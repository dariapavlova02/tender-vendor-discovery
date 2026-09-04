import pytest

from vendor_ai_agent.enrichment_providers.website_content import WebsiteContentProvider
from vendor_ai_agent.models import VendorRecord


class DummyScraper:
    def scrape(self, url):  # pragma: no cover - should not be called
        raise AssertionError("scrape should not be invoked for social domains")


def test_social_domains_skipped():
    provider = WebsiteContentProvider(scraper=DummyScraper(), enable_logging=False)
    urls = [
        "https://www.facebook.com/acme",
        "https://brand-example.squarespace.com/contact",
    ]

    for url in urls:
        vendor = VendorRecord(company_name="ACME", website=url)
        enriched = provider.enrich(vendor)

        assert enriched.filtering_metadata["scrape_status"] == "ignored_social"
        assert enriched.filtering_metadata["scrape_error"] == "Social profile link"
        assert enriched.filtering_metadata["social_profile_url"] == url
        assert "website_content" not in enriched.filtering_metadata


def test_regular_domain_still_scrapes(monkeypatch):
    class FakeResult:
        status = "success"
        content = "hello"
        timestamp = "now"
        source_url = "https://example.com"
        error_message = None

    class FakeScraper:
        def __init__(self):
            self.called = False

        def scrape(self, url):
            self.called = True
            assert url == "https://example.com"
            return FakeResult()

    scraper = FakeScraper()
    provider = WebsiteContentProvider(scraper=scraper, enable_logging=False)
    vendor = VendorRecord(company_name="Example", website="https://example.com")

    enriched = provider.enrich(vendor)

    assert scraper.called is True
    assert enriched.filtering_metadata["website_content"] == "hello"
