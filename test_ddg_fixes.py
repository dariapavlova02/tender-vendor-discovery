"""
Test DuckDuckGo fixes for rate limiting bypass
"""
import time
import requests
import random

def test_direct_ddg():
    """Test direct DDG request with all fixes"""
    print("=" * 60)
    print("Testing Direct DuckDuckGo Request")
    print("=" * 60)
    
    query = "Kelly Services Toronto Canada"
    
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://duckduckgo.com/",
        "Connection": "close",
    }
    
    print(f"\n1. Query: {query}")
    print(f"2. URL: {url}")
    print(f"3. Headers: {headers}")
    print(f"4. allow_redirects: False")
    print(f"5. Using params dict for proper encoding")
    
    try:
        response = requests.get(
            url,
            params={"q": query},
            headers=headers,
            allow_redirects=False,
            timeout=15
        )
        
        print(f"\n✓ Status Code: {response.status_code}")
        print(f"✓ Content Length: {len(response.text)} bytes")
        
        if response.status_code == 200:
            print("✓ SUCCESS: Got 200 OK")
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            result_divs = soup.find_all("div", class_="result")
            
            print(f"✓ Found {len(result_divs)} search results")
            
            if result_divs:
                first = result_divs[0]
                title_elem = first.find("a", class_="result__a")
                if title_elem:
                    print(f"\n  First result: {title_elem.get_text(strip=True)[:100]}")
            
            return True
            
        elif response.status_code == 202:
            print("✗ STILL RATE LIMITED (202)")
            return False
            
        elif response.status_code == 302:
            print(f"⚠ Got 302 redirect to: {response.headers.get('Location')}")
            return False
            
        else:
            print(f"⚠ Unexpected status: {response.status_code}")
            return False
            
    except Exception as exc:
        print(f"✗ ERROR: {exc}")
        return False


def test_multiple_requests():
    """Test 5 requests with jitter to see if we avoid ban"""
    print("\n" + "=" * 60)
    print("Testing Multiple Requests with Jitter")
    print("=" * 60)
    
    test_queries = [
        "Kelly Services Toronto Canada",
        "HubSpoke Ottawa Canada",
        "Promaxis Systems Montreal Canada",
        "TeamBuilder Consulting Vancouver Canada",
        "GDIT Arlington USA",
    ]
    
    base_delay = 3.0
    success_count = 0
    
    for i, query in enumerate(test_queries, 1):
        jitter = random.uniform(0, 1.0)
        delay = base_delay + jitter
        
        if i > 1:
            print(f"\n⏱ Waiting {delay:.2f} seconds...")
            time.sleep(delay)
        
        print(f"\n--- Request {i}/5: {query} ---")
        
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://duckduckgo.com/",
            "Connection": "close",
        }
        
        try:
            response = requests.get(
                url,
                params={"q": query},
                headers=headers,
                allow_redirects=False,
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"  ✓ Success: {response.status_code}")
                success_count += 1
            elif response.status_code == 202:
                print(f"  ✗ Rate limited: {response.status_code}")
                break
            else:
                print(f"  ⚠ Status: {response.status_code}")
                
        except Exception as exc:
            print(f"  ✗ Error: {exc}")
    
    print(f"\n{'=' * 60}")
    print(f"Result: {success_count}/5 requests successful")
    print(f"{'=' * 60}")
    
    return success_count == 5


def check_current_status():
    """Check if we're currently banned"""
    print("=" * 60)
    print("Checking Current DuckDuckGo Status")
    print("=" * 60)
    
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": "test"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            allow_redirects=False,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✓ Status: Not banned (200 OK)")
            return True
        elif response.status_code == 202:
            print("✗ Status: Currently banned (202)")
            return False
        else:
            print(f"⚠ Status: {response.status_code}")
            return False
            
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return False


if __name__ == "__main__":
    print("\n🔧 DuckDuckGo Anti-Ban Fix Test\n")
    
    if not check_current_status():
        print("\n⏳ IP currently banned. Wait 15-30 minutes and retry.")
        print("   Check with: curl https://html.duckduckgo.com/html/?q=test")
        exit(1)
    
    print("\n")
    
    test1 = test_direct_ddg()
    
    if test1:
        print("\n")
        test2 = test_multiple_requests()
        
        if test2:
            print("\n✅ ALL TESTS PASSED - Fixes are working!")
        else:
            print("\n⚠️ Single request OK, but got banned on multiple requests")
    else:
        print("\n❌ Single request failed - fixes may not be working")
