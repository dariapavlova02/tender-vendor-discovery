"""
Test Serper API (Google Search) for website/contact discovery
Alternative to DuckDuckGo while IP is banned
"""
import http.client
import json
import time

API_KEY = "259584d5d8cbcf2055f380aaa4d5d1aae0763ac4"

def serper_search(query):
    """Search using Serper API"""
    conn = http.client.HTTPSConnection("google.serper.dev")
    
    payload = json.dumps({
        "q": query,
        "num": 10  # Get 10 results
    })
    
    headers = {
        'X-API-KEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        conn.request("POST", "/search", payload, headers)
        res = conn.getresponse()
        data = res.read()
        
        return json.loads(data.decode("utf-8"))
    
    except Exception as exc:
        return {"error": str(exc)}
    
    finally:
        conn.close()


def test_website_discovery():
    """Test 1: Website Discovery for Real Companies"""
    print("=" * 80)
    print("TEST 1: Website Discovery")
    print("=" * 80)
    
    test_companies = [
        {"name": "Kelly Services", "city": "Toronto", "country": "Canada"},
        {"name": "Promaxis Systems", "city": "Montreal", "country": "Canada"},
        {"name": "HubSpoke", "city": "Ottawa", "country": "Canada"},
        {"name": "GDIT", "city": "Arlington", "country": "USA"},
        {"name": "TeamBuilder Consulting", "city": "Vancouver", "country": "Canada"},
    ]
    
    results = []
    
    for company in test_companies:
        query = f"{company['name']} {company['city']} {company['country']}"
        
        print(f"\n{'─' * 80}")
        print(f"Query: {query}")
        print(f"{'─' * 80}")
        
        response = serper_search(query)
        
        if "error" in response:
            print(f"❌ Error: {response['error']}")
            results.append({"company": company['name'], "website": None, "error": response['error']})
            continue
        
        # Extract organic results
        organic = response.get("organic", [])
        
        if not organic:
            print(f"⚠️  No results found")
            results.append({"company": company['name'], "website": None, "error": "No results"})
            continue
        
        # Show first 3 results
        print(f"✓ Found {len(organic)} results\n")
        
        for i, result in enumerate(organic[:3], 1):
            title = result.get("title", "N/A")
            link = result.get("link", "N/A")
            snippet = result.get("snippet", "")[:100]
            
            print(f"  {i}. {title}")
            print(f"     URL: {link}")
            print(f"     Snippet: {snippet}...")
            print()
        
        # Take first result as website
        best_result = organic[0]
        website = best_result.get("link")
        
        results.append({
            "company": company['name'],
            "website": website,
            "title": best_result.get("title"),
            "position": 1
        })
        
        time.sleep(1)  # Rate limit
    
    print("\n" + "=" * 80)
    print("SUMMARY: Website Discovery")
    print("=" * 80)
    
    for r in results:
        status = "✓" if r.get("website") else "✗"
        print(f"{status} {r['company']:30s} → {r.get('website', 'NOT FOUND')}")
    
    success_rate = len([r for r in results if r.get("website")]) / len(results) * 100
    print(f"\nSuccess Rate: {success_rate:.0f}% ({len([r for r in results if r.get('website')])}/{len(results)})")
    
    return results


def test_email_discovery():
    """Test 2: Email Discovery (search for contact/email directly)"""
    print("\n\n" + "=" * 80)
    print("TEST 2: Email Discovery")
    print("=" * 80)
    
    test_queries = [
        "Kelly Services Toronto contact email",
        "Promaxis Systems Montreal email address",
        "HubSpoke Ottawa contact info",
        "GDIT Arlington contact email",
        "TeamBuilder Consulting Vancouver email",
    ]
    
    results = []
    
    for query in test_queries:
        print(f"\n{'─' * 80}")
        print(f"Query: {query}")
        print(f"{'─' * 80}")
        
        response = serper_search(query)
        
        if "error" in response:
            print(f"❌ Error: {response['error']}")
            results.append({"query": query, "emails": [], "error": response['error']})
            continue
        
        # Look for emails in snippets
        organic = response.get("organic", [])
        
        emails_found = []
        
        for result in organic[:5]:
            snippet = result.get("snippet", "")
            title = result.get("title", "")
            link = result.get("link", "")
            
            # Simple email regex
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            
            emails_in_snippet = re.findall(email_pattern, snippet)
            emails_in_title = re.findall(email_pattern, title)
            
            if emails_in_snippet or emails_in_title:
                all_emails = emails_in_snippet + emails_in_title
                emails_found.extend(all_emails)
                print(f"  ✓ Found in: {link[:60]}")
                print(f"    Emails: {', '.join(all_emails)}")
        
        if not emails_found:
            print(f"  ✗ No emails found in snippets")
        
        results.append({
            "query": query,
            "emails": list(set(emails_found)),
            "count": len(set(emails_found))
        })
        
        time.sleep(1)
    
    print("\n" + "=" * 80)
    print("SUMMARY: Email Discovery")
    print("=" * 80)
    
    for r in results:
        status = "✓" if r['count'] > 0 else "✗"
        emails_str = ", ".join(r['emails']) if r['emails'] else "NOT FOUND"
        print(f"{status} {r['query']:50s} → {emails_str}")
    
    success_rate = len([r for r in results if r['count'] > 0]) / len(results) * 100
    print(f"\nSuccess Rate: {success_rate:.0f}% ({len([r for r in results if r['count'] > 0])}/{len(results)})")
    
    return results


def test_phone_discovery():
    """Test 3: Phone Discovery"""
    print("\n\n" + "=" * 80)
    print("TEST 3: Phone Discovery")
    print("=" * 80)
    
    test_queries = [
        "Kelly Services Toronto phone number",
        "Promaxis Systems Montreal contact phone",
        "HubSpoke Ottawa phone",
        "GDIT Arlington phone number",
        "TeamBuilder Consulting Vancouver phone",
    ]
    
    results = []
    
    for query in test_queries:
        print(f"\n{'─' * 80}")
        print(f"Query: {query}")
        print(f"{'─' * 80}")
        
        response = serper_search(query)
        
        if "error" in response:
            print(f"❌ Error: {response['error']}")
            results.append({"query": query, "phones": [], "error": response['error']})
            continue
        
        # Look for phone numbers in snippets
        organic = response.get("organic", [])
        
        phones_found = []
        
        for result in organic[:5]:
            snippet = result.get("snippet", "")
            title = result.get("title", "")
            link = result.get("link", "")
            
            # Phone regex (US/Canada format)
            import re
            phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'
            
            phones_in_snippet = re.findall(phone_pattern, snippet)
            phones_in_title = re.findall(phone_pattern, title)
            
            if phones_in_snippet or phones_in_title:
                all_phones = [f"({m[0]}) {m[1]}-{m[2]}" for m in phones_in_snippet + phones_in_title]
                phones_found.extend(all_phones)
                print(f"  ✓ Found in: {link[:60]}")
                print(f"    Phones: {', '.join(all_phones)}")
        
        if not phones_found:
            print(f"  ✗ No phones found in snippets")
        
        results.append({
            "query": query,
            "phones": list(set(phones_found)),
            "count": len(set(phones_found))
        })
        
        time.sleep(1)
    
    print("\n" + "=" * 80)
    print("SUMMARY: Phone Discovery")
    print("=" * 80)
    
    for r in results:
        status = "✓" if r['count'] > 0 else "✗"
        phones_str = ", ".join(r['phones']) if r['phones'] else "NOT FOUND"
        print(f"{status} {r['query']:50s} → {phones_str}")
    
    success_rate = len([r for r in results if r['count'] > 0]) / len(results) * 100
    print(f"\nSuccess Rate: {success_rate:.0f}% ({len([r for r in results if r['count'] > 0])}/{len(results)})")
    
    return results


def check_api_status():
    """Check API status and limits"""
    print("=" * 80)
    print("Checking Serper API Status")
    print("=" * 80)
    
    response = serper_search("test query")
    
    if "error" in response:
        print(f"❌ API Error: {response['error']}")
        return False
    
    print("✓ API is working")
    
    # Check for rate limit info in response
    search_info = response.get("searchInformation", {})
    print(f"  Total results available: {search_info.get('totalResults', 'N/A')}")
    print(f"  Search time: {search_info.get('formattedSearchTime', 'N/A')} sec")
    
    return True


if __name__ == "__main__":
    print("\n🔍 SERPER API TEST (Google Search Alternative)")
    print("=" * 80)
    
    # Check API first
    if not check_api_status():
        print("\n❌ API not working, exiting")
        exit(1)
    
    print("\n")
    
    # Run tests
    website_results = test_website_discovery()
    email_results = test_email_discovery()
    phone_results = test_phone_discovery()
    
    # Final summary
    print("\n\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    website_success = len([r for r in website_results if r.get('website')]) / len(website_results) * 100
    email_success = len([r for r in email_results if r['count'] > 0]) / len(email_results) * 100
    phone_success = len([r for r in phone_results if r['count'] > 0]) / len(phone_results) * 100
    
    print(f"Website Discovery: {website_success:.0f}% ({len([r for r in website_results if r.get('website')])}/{len(website_results)})")
    print(f"Email Discovery:   {email_success:.0f}% ({len([r for r in email_results if r['count'] > 0])}/{len(email_results)})")
    print(f"Phone Discovery:   {phone_success:.0f}% ({len([r for r in phone_results if r['count'] > 0])}/{len(phone_results)})")
    
    print("\n💡 Recommendations:")
    if website_success >= 80:
        print("  ✓ Serper API is EXCELLENT for website discovery")
    if email_success >= 40:
        print("  ✓ Serper API is GOOD for email discovery")
    else:
        print("  ⚠ Serper API has LOW email snippet coverage")
    if phone_success >= 40:
        print("  ✓ Serper API is GOOD for phone discovery")
    else:
        print("  ⚠ Serper API has LOW phone snippet coverage")
    
    print("\n📊 Serper API Info:")
    print("  - Free tier: 2,500 searches/month")
    print("  - Cost: $50/month for 5,000 searches")
    print("  - No rate limiting issues (unlike DuckDuckGo)")
    print("  - Official Google Search results")
