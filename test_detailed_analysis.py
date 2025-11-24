"""Detailed analysis of contact extraction for each website."""
import sys
import logging
import re
from src.vendor_ai_agent.modules.website_scraper import WebsiteScraper
from src.vendor_ai_agent.modules.contact_extractor import ContactExtractor
from src.vendor_ai_agent.modules.llm_providers import OpenAIProvider

# Setup logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def analyze_website(url: str):
    """Deep analysis of a single website."""
    print(f"\n{'='*80}")
    print(f"🔍 ANALYZING: {url}")
    print('='*80)
    
    scraper = WebsiteScraper(timeout_seconds=15)
    
    # Step 1: Check which contact pages exist
    print("\n📄 STEP 1: Checking contact page paths...")
    contact_paths = scraper.CONTACT_PATHS
    found_paths = []
    
    for path in contact_paths[:4]:  # Check first 4 paths
        from urllib.parse import urljoin
        import requests
        target_url = urljoin(url, path)
        try:
            r = requests.get(target_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200 and len(r.content) > 200:
                found_paths.append(path)
                print(f"  ✓ {path}: Found ({len(r.content)} bytes)")
        except:
            print(f"  ✗ {path}: Failed")
    
    if not found_paths:
        print("  ⚠️  No contact pages found!")
        return
    
    # Step 2: Scrape the first found contact page
    print(f"\n📥 STEP 2: Scraping {found_paths[0]}...")
    from urllib.parse import urljoin
    target_url = urljoin(url, found_paths[0])
    
    try:
        text = scraper._fetch_page(target_url, preserve_contacts=True)
        print(f"  Extracted {len(text)} chars of text")
        
        if len(text) < 100:
            print(f"  ⚠️  Text too short! Content: '{text}'")
            return
            
        # Show preview
        print(f"\n  Preview (first 300 chars):")
        print(f"  {text[:300]}")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return
    
    # Step 3: Manual regex extraction
    print(f"\n🔎 STEP 3: Running regex patterns...")
    
    # Email regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    raw_emails = re.findall(email_pattern, text, re.IGNORECASE)
    print(f"  Raw emails found: {len(raw_emails)}")
    if raw_emails:
        for email in raw_emails[:5]:
            print(f"    - {email}")
    
    # Phone regex patterns
    phone_patterns = [
        r'\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}',
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        r'\b\d{3}\.\d{3}\.\d{4}\b',
    ]
    
    all_phones = []
    for pattern in phone_patterns:
        phones = re.findall(pattern, text)
        all_phones.extend(phones)
    
    print(f"  Raw phones found: {len(all_phones)}")
    if all_phones:
        for phone in all_phones[:5]:
            print(f"    - {phone}")
    
    # Step 4: Check spam filtering
    print(f"\n🚫 STEP 4: Checking spam filtering...")
    spam_patterns = [
        'example.com', 'test@', 'noreply@', 'donotreply@',
        'webmaster@', 'abuse@', 'postmaster@', 'admin@',
        'no-reply@', 'bounce@', 'mailer@'
    ]
    
    filtered_emails = []
    for email in raw_emails:
        is_spam = any(pattern in email.lower() for pattern in spam_patterns)
        if is_spam:
            print(f"  ✗ Filtered out: {email} (spam)")
        else:
            filtered_emails.append(email)
    
    print(f"  Valid emails after filtering: {len(filtered_emails)}")
    
    # Step 5: Run full ContactExtractor
    print(f"\n🤖 STEP 5: Running ContactExtractor...")
    llm_provider = OpenAIProvider(default_model="gpt-4o-mini")
    extractor = ContactExtractor(llm_provider=llm_provider)
    
    result = extractor.extract(text, use_llm_fallback=True)
    
    print(f"  Method: {result.extraction_method}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Emails: {result.emails}")
    print(f"  Phones: {result.phones}")
    print(f"  Names: {result.contact_names}")
    
    # Step 6: Summary
    print(f"\n📊 SUMMARY:")
    if result.emails or result.phones:
        print(f"  ✅ SUCCESS - Found {len(result.emails)} emails, {len(result.phones)} phones")
    else:
        print(f"  ❌ FAILED - No contacts extracted")
        
        # Diagnose why
        if len(text) < 100:
            print(f"  Reason: Page content too short")
        elif not found_paths:
            print(f"  Reason: No contact pages found")
        elif not raw_emails and not all_phones:
            print(f"  Reason: No email/phone patterns in text")
        elif raw_emails and not filtered_emails:
            print(f"  Reason: All emails filtered as spam")
        else:
            print(f"  Reason: Unknown - needs manual investigation")


if __name__ == "__main__":
    # Test the 6 websites with detailed analysis
    test_urls = [
        "https://www.atdtechnology.com/",      # SUCCESS
        "https://www.boozallen.com/",          # FAILED
        "https://www.leidos.com/",             # SUCCESS (phone only)
        "https://www.gdit.com/",               # FAILED
        "https://www.saic.com/",               # SUCCESS (phone only)
        "https://www.caci.com/",               # FAILED
    ]
    
    for url in test_urls:
        try:
            analyze_website(url)
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
