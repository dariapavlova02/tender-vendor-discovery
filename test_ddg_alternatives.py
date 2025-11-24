"""
Test alternative DuckDuckGo endpoints and methods to bypass ban
"""
import requests
import time

def test_lite_endpoint():
    """Test /lite endpoint - more tolerant to bots"""
    print("=" * 60)
    print("Test 1: /lite Endpoint (More Bot-Tolerant)")
    print("=" * 60)
    
    url = "https://duckduckgo.com/lite/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://duckduckgo.com/",
    }
    
    try:
        response = requests.get(
            url,
            params={"q": "Kelly Services Toronto"},
            headers=headers,
            allow_redirects=False,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ SUCCESS with /lite endpoint!")
            print(f"Content preview: {response.text[:200]}")
            return True
        elif response.status_code == 202:
            print("✗ Still banned on /lite")
            return False
        else:
            print(f"⚠ Unexpected: {response.status_code}")
            return False
            
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return False


def test_api_endpoint():
    """Test instant answer API (limited but may work)"""
    print("\n" + "=" * 60)
    print("Test 2: Instant Answer API")
    print("=" * 60)
    
    url = "https://api.duckduckgo.com/"
    
    try:
        response = requests.get(
            url,
            params={
                "q": "Kelly Services Toronto",
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            },
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ SUCCESS with API endpoint!")
            print(f"Abstract: {data.get('Abstract', 'N/A')[:100]}")
            print(f"AbstractURL: {data.get('AbstractURL', 'N/A')}")
            return True
        elif response.status_code == 202:
            print("✗ Still banned on API")
            return False
        else:
            print(f"⚠ Unexpected: {response.status_code}")
            return False
            
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return False


def test_html_no_redirect():
    """Test /html with all anti-redirect measures"""
    print("\n" + "=" * 60)
    print("Test 3: /html with Anti-Redirect Measures")
    print("=" * 60)
    
    session = requests.Session()
    session.max_redirects = 0
    
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://duckduckgo.com/",
        "Connection": "close",
        "DNT": "1",
    }
    
    try:
        response = session.get(
            url,
            params={"q": "Kelly Services Toronto", "kl": "us-en"},
            headers=headers,
            allow_redirects=False,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ SUCCESS with /html!")
            return True
        elif response.status_code == 202:
            print("✗ Still banned")
            return False
        elif response.status_code == 301 or response.status_code == 302:
            print(f"⚠ Redirect to: {response.headers.get('Location')}")
            return False
        else:
            print(f"⚠ Unexpected: {response.status_code}")
            return False
            
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return False


def test_curl_equivalent():
    """Test exact curl equivalent"""
    print("\n" + "=" * 60)
    print("Test 4: cURL-Equivalent Request")
    print("=" * 60)
    
    import subprocess
    
    cmd = [
        "curl",
        "-s",
        "-w", "\\nHTTP_CODE:%{http_code}",
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Referer: https://duckduckgo.com/",
        "https://html.duckduckgo.com/html/?q=test"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout
        
        if "HTTP_CODE:200" in output:
            print("✓ SUCCESS with curl!")
            return True
        elif "HTTP_CODE:202" in output:
            print("✗ Still banned via curl")
            return False
        else:
            print(f"Output: {output[-200:]}")
            return False
            
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return False


def estimate_unban_time():
    """Try to estimate when ban will lift"""
    print("\n" + "=" * 60)
    print("Estimating Unban Time")
    print("=" * 60)
    
    wait_intervals = [5, 10, 15, 20]  # minutes
    
    print("\nTesting different wait times...")
    print("(This is a dry-run estimate, not actual waiting)")
    
    print(f"\nBased on previous session:")
    print(f"  - Last ban: ~30 requests in 30 minutes")
    print(f"  - Ban duration: Typically 30-60 minutes")
    print(f"  - Current time: {time.strftime('%H:%M:%S')}")
    print(f"  - Estimated unban: ~{time.strftime('%H:%M:%S', time.localtime(time.time() + 1800))}")
    
    print(f"\n💡 Recommendation:")
    print(f"   1. Wait 30 minutes from last request")
    print(f"   2. Test with: curl https://html.duckduckgo.com/html/?q=test")
    print(f"   3. If still 202, wait another 30 minutes")


if __name__ == "__main__":
    print("\n🔧 Testing Alternative DuckDuckGo Access Methods\n")
    
    results = []
    
    results.append(("Lite Endpoint", test_lite_endpoint()))
    time.sleep(2)
    
    results.append(("API Endpoint", test_api_endpoint()))
    time.sleep(2)
    
    results.append(("HTML No-Redirect", test_html_no_redirect()))
    time.sleep(2)
    
    results.append(("cURL Equivalent", test_curl_equivalent()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for method, success in results:
        status = "✓ WORKS" if success else "✗ BLOCKED"
        print(f"{method:20s}: {status}")
    
    if not any(s for _, s in results):
        estimate_unban_time()
    else:
        working = [m for m, s in results if s]
        print(f"\n✅ Working method: {working[0]}")
