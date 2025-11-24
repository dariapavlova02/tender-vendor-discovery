"""Test contact extraction on real vendor websites."""
import sys
import logging
from src.vendor_ai_agent.modules.website_scraper import WebsiteScraper
from src.vendor_ai_agent.modules.contact_extractor import ContactExtractor
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

def test_website(url: str):
    """Test contact extraction on a single website."""
    print(f"\n{'='*70}")
    print(f"🔍 TESTING: {url}")
    print('='*70)
    
    # Initialize with LLM support
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini")
    scraper = WebsiteScraper(timeout_seconds=15)
    extractor = ContactExtractor(llm_provider=llm_provider)
    
    # Scrape and extract
    result = scraper.scrape_contacts(url, extractor)
    
    # Display results
    print(f"\n📊 RESULTS:")
    print(f"  Method: {result.extraction_method}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"\n📧 Emails ({len(result.emails)}):")
    for i, email in enumerate(result.emails, 1):
        source = result.email_sources[i-1] if i-1 < len(result.email_sources) else 'unknown'
        print(f"  {i}. {email} [{source}]")
    
    print(f"\n📞 Phones ({len(result.phones)}):")
    for i, phone in enumerate(result.phones, 1):
        source = result.phone_sources[i-1] if i-1 < len(result.phone_sources) else 'unknown'
        print(f"  {i}. {phone} [{source}]")
    
    print(f"\n👤 Contact Names ({len(result.contact_names)}):")
    for i, name in enumerate(result.contact_names, 1):
        print(f"  {i}. {name}")
    
    # Summary
    print(f"\n✅ SUCCESS" if result.emails or result.phones else "❌ NO CONTACTS FOUND")
    return result

if __name__ == "__main__":
    # Test multiple real vendor websites
    test_urls = [
        "https://www.atdtechnology.com/",
        "https://www.boozallen.com/",
        "https://www.leidos.com/",
        "https://www.gdit.com/",
        "https://www.saic.com/",
        "https://www.caci.com/",
    ]
    
    results = []
    for url in test_urls:
        try:
            result = test_website(url)
            results.append((url, result))
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Final summary
    print(f"\n{'='*70}")
    print("📈 FINAL SUMMARY")
    print('='*70)
    
    success_count = sum(1 for _, r in results if r.emails or r.phones)
    print(f"Tested: {len(results)} websites")
    print(f"Success: {success_count}/{len(results)} ({success_count/len(results)*100:.0f}%)")
    print(f"\nMethods used:")
    methods = {}
    for _, r in results:
        methods[r.extraction_method] = methods.get(r.extraction_method, 0) + 1
    for method, count in methods.items():
        print(f"  {method}: {count}")
