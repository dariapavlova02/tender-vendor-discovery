"""
Auto-retry script to test when DuckDuckGo unban happens
Run this and leave it - it will check every 5 minutes
"""
import requests
import time
from datetime import datetime

def check_ddg_status():
    """Check if DDG is accessible"""
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": "test"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://duckduckgo.com/",
                "Connection": "close",
            },
            allow_redirects=False,
            timeout=10
        )
        
        return response.status_code
        
    except Exception as exc:
        return f"Error: {exc}"


def wait_for_unban(check_interval=300):
    """Wait until DDG unbans us, checking every interval seconds"""
    
    print("🔄 DuckDuckGo Unban Monitor")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Check interval: {check_interval} seconds ({check_interval//60} min)")
    print("=" * 60)
    
    attempt = 1
    
    while True:
        status = check_ddg_status()
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if status == 200:
            print(f"\n[{timestamp}] ✅ UNBANNED! Status: {status}")
            print("\n🎉 DuckDuckGo is now accessible!")
            print("\nNext steps:")
            print("  1. Run: python test_ddg_fixes.py")
            print("  2. If successful, run 100-vendor test")
            print("  3. Then proceed with production enrichment")
            return True
            
        elif status == 202:
            print(f"[{timestamp}] ⏳ Attempt {attempt}: Still banned (202)", end='\r')
            
        else:
            print(f"[{timestamp}] ⚠️  Attempt {attempt}: Status {status}")
        
        attempt += 1
        time.sleep(check_interval)


if __name__ == "__main__":
    initial_status = check_ddg_status()
    
    if initial_status == 200:
        print("✅ DuckDuckGo is already accessible!")
        print("\nRun test: python test_ddg_fixes.py")
    else:
        print(f"Current status: {initial_status}")
        print("\nWaiting for unban (checks every 5 minutes)...")
        print("Press Ctrl+C to stop monitoring\n")
        
        try:
            wait_for_unban(check_interval=300)
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
            print(f"Last check: {datetime.now().strftime('%H:%M:%S')}")
