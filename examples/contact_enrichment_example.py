"""Example: How to use contact enrichment in your pipeline."""
from pathlib import Path

from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.pipeline import VendorAIPipeline

# Configure contact scraping
config = RuntimeConfig()
config.enrichment.enable_contact_scraping = True  # Enable web scraping
config.enrichment.enable_llm_fallback = True      # Use LLM for complex cases
config.enrichment.scraper_timeout_seconds = 10    # Timeout per page

# Run pipeline
pipeline = VendorAIPipeline(config)
artifacts = pipeline.run([Path("tender.pdf")])

# Check contact quality
for vendor in artifacts.enriched_vendors:
    email_source = vendor.filtering_metadata.get("email_source", "unknown")
    email_conf = vendor.filtering_metadata.get("email_confidence", 0)
    
    print(f"{vendor.company_name}")
    print(f"  Email: {vendor.email} (source: {email_source}, confidence: {email_conf})")
    
    if email_source == "scraped_regex":
        print("  ✓ High quality - extracted via regex")
    elif email_source == "scraped_llm":
        print("  ~ Medium quality - extracted via LLM")
    elif email_source == "fallback_static":
        print("  ⚠ Low quality - generated fallback")
    
    # All alternative contacts
    if "all_emails" in vendor.filtering_metadata:
        alternatives = vendor.filtering_metadata["all_emails"]
        print(f"  Alternative emails: {', '.join(alternatives[1:])}")
    
    if "contact_names" in vendor.filtering_metadata:
        names = vendor.filtering_metadata["contact_names"]
        print(f"  Contact persons: {', '.join(names)}")
    
    print()

# Filter by confidence
high_quality = [
    v for v in artifacts.enriched_vendors
    if v.filtering_metadata.get("email_confidence", 0) >= 0.7
]

print(f"High quality contacts: {len(high_quality)}/{len(artifacts.enriched_vendors)}")

# Disable contact scraping (use only static fallbacks)
config.enrichment.enable_contact_scraping = False
pipeline = VendorAIPipeline(config)
artifacts = pipeline.run([Path("tender.pdf")])
