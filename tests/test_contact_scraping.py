"""Test contact scraping end-to-end."""
from __future__ import annotations

import pytest

from vendor_ai_agent.enrichment_providers.contact_scraping import ContactScrapingProvider
from vendor_ai_agent.models import VendorRecord
from vendor_ai_agent.modules.contact_extractor import ContactExtractor
from vendor_ai_agent.modules.tender_profiler import LLMProvider, OpenAIProvider
from vendor_ai_agent.modules.website_scraper import WebsiteScraper


def test_contact_extractor_regex():
    """Test regex-based contact extraction."""
    extractor = ContactExtractor(llm_provider=None)
    
    sample_text = """
    Contact Us
    For sales inquiries: sales@example.com
    For support: support@example.com
    Phone: (555) 123-4567
    Alternative: 555-987-6543
    Sales Manager: John Smith
    VP of Sales: Jane Doe
    """
    
    contacts = extractor.extract(sample_text, use_llm_fallback=False)
    
    assert len(contacts.emails) > 0
    assert "sales@example.com" in contacts.emails
    assert contacts.emails[0] == "sales@example.com"
    
    assert len(contacts.phones) > 0
    assert contacts.extraction_method == "regex"
    assert contacts.confidence >= 0.7


def test_contact_extractor_prioritization():
    """Test email prioritization logic."""
    extractor = ContactExtractor(llm_provider=None)
    
    text = "contact@test.com support@test.com sales@test.com info@test.com"
    
    contacts = extractor.extract(text, use_llm_fallback=False)
    
    assert contacts.emails[0] == "sales@test.com"


def test_contact_extractor_spam_filtering():
    """Test that spam emails are filtered out."""
    extractor = ContactExtractor(llm_provider=None)
    
    text = "noreply@test.com webmaster@test.com real@test.com test@example.com"
    
    contacts = extractor.extract(text, use_llm_fallback=False)
    
    assert "noreply@test.com" not in contacts.emails
    assert "webmaster@test.com" not in contacts.emails
    assert "test@example.com" not in contacts.emails
    assert "real@test.com" in contacts.emails


def test_phone_normalization():
    """Test phone number normalization to E.164."""
    extractor = ContactExtractor(llm_provider=None)
    
    text = "(555) 123-4567 555-987-6543 555.111.2222"
    
    contacts = extractor.extract(text, use_llm_fallback=False)
    
    for phone in contacts.phones:
        assert phone.startswith("+1")
        assert len(phone) == 12


@pytest.mark.skip(reason="Requires real website, run manually")
def test_website_scraper_contact_pages():
    """Test scraping real contact pages."""
    scraper = WebsiteScraper(timeout_seconds=10)
    extractor = ContactExtractor(llm_provider=None)
    
    contacts = scraper.scrape_contacts("https://example.com", extractor)
    
    assert contacts is not None


@pytest.mark.skip(reason="Requires OpenAI API key")
def test_llm_fallback():
    """Test LLM fallback for complex HTML."""
    llm_provider = OpenAIProvider(model="gpt-4o-mini")
    extractor = ContactExtractor(llm_provider=llm_provider)
    
    complex_text = """
    <div class='contact'>
        <script>document.write('info' + '@' + 'example.com')</script>
        <a href='tel:5551234567'>Call us</a>
    </div>
    """
    
    contacts = extractor.extract(complex_text, use_llm_fallback=True)
    
    assert contacts.extraction_method in ["llm", "llm_failed"]


def test_contact_scraping_provider_skip_existing():
    """Test that provider skips vendors with real contacts."""
    llm_provider = OpenAIProvider(model="gpt-4o-mini")
    provider = ContactScrapingProvider(llm_provider=llm_provider)
    
    vendor = VendorRecord(
        company_name="Test Corp",
        email="real@testcorp.com",
        phone="+15551234567",
        website="https://testcorp.com",
        filtering_metadata={
            "email_source": "scraped_regex",
            "phone_source": "scraped_regex"
        }
    )
    
    enriched = provider.enrich(vendor)
    
    assert enriched.email == "real@testcorp.com"
    assert "contact_scraping" not in enriched.enrichment_flags


def test_contact_scraping_provider_metadata():
    """Test that provider adds metadata correctly."""
    llm_provider = OpenAIProvider(model="gpt-4o-mini")
    provider = ContactScrapingProvider(llm_provider=llm_provider, enable_llm_fallback=False)
    
    vendor = VendorRecord(
        company_name="Test Corp",
        website="https://example.com"
    )
    
    enriched = provider.enrich(vendor)
    
    if "email_source" in enriched.filtering_metadata:
        assert enriched.filtering_metadata["email_source"] in [
            "scraped_regex", "scraped_llm", "no_contact_page"
        ]


def test_static_contacts_fallback_metadata():
    """Test that StaticContactsProvider adds fallback metadata."""
    from vendor_ai_agent.enrichment_providers import StaticContactsProvider
    
    provider = StaticContactsProvider()
    
    vendor = VendorRecord(
        company_name="Test Corp",
        website="https://testcorp.com"
    )
    
    enriched = provider.enrich(vendor)
    
    assert enriched.email.startswith("info@")
    assert enriched.filtering_metadata["email_source"] == "fallback_static"
    assert enriched.filtering_metadata["email_confidence"] == 0.1
    
    assert enriched.phone == "N/A"
    assert enriched.filtering_metadata["phone_source"] == "fallback_na"
    assert enriched.filtering_metadata["phone_confidence"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
