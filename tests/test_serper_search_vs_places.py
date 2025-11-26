"""
Test script: Serper Search API vs Places API comparison
Goal: Validate which API provides better vendor discovery results
"""

import os
import json
import time
from dataclasses import dataclass
from typing import List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

@dataclass
class VendorResult:
    """Unified vendor result from either API."""
    name: str
    domain: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    rating: Optional[float]
    rating_count: Optional[int]
    google_cid: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    categories: List[str]
    source_api: str  # "search" or "places"


class SerperAPIComparison:
    """Compare Search API vs Places API for vendor discovery."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.search_url = "https://google.serper.dev/search"
        self.places_url = "https://google.serper.dev/places"
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
    
    def search_api(self, query: str, num_results: int = 10) -> dict:
        """Current approach: Search API."""
        payload = {"q": query, "num": num_results}
        start_time = time.time()
        
        response = requests.post(
            self.search_url,
            headers=self.headers,
            json=payload,
            timeout=10
        )
        
        elapsed = time.time() - start_time
        response.raise_for_status()
        data = response.json()
        
        return {
            "data": data,
            "elapsed_seconds": elapsed,
            "api": "search"
        }
    
    def places_api(self, query: str, num_results: int = 10) -> dict:
        """Proposed approach: Places API."""
        payload = {"q": query, "max": num_results}
        start_time = time.time()
        
        response = requests.post(
            self.places_url,
            headers=self.headers,
            json=payload,
            timeout=10
        )
        
        elapsed = time.time() - start_time
        response.raise_for_status()
        data = response.json()
        
        return {
            "data": data,
            "elapsed_seconds": elapsed,
            "api": "places"
        }
    
    def batch_places_api(self, queries: List[str], num_results_per_query: int = 10) -> Optional[dict]:
        """Test batch Places API (if available)."""
        # Note: Need to verify if batch endpoint exists
        # If not, we'll simulate by doing multiple sequential calls
        payload = {
            "queries": [{"q": q, "max": num_results_per_query} for q in queries]
        }
        start_time = time.time()
        
        try:
            response = requests.post(
                self.places_url + "/batch",  # Hypothetical endpoint
                headers=self.headers,
                json=payload,
                timeout=30
            )
            elapsed = time.time() - start_time
            response.raise_for_status()
            data = response.json()
            
            return {
                "data": data,
                "elapsed_seconds": elapsed,
                "api": "places_batch",
                "query_count": len(queries)
            }
        except Exception as e:
            print(f"Batch endpoint not available: {e}")
            return None
    
    def parse_search_results(self, data: dict) -> List[VendorResult]:
        """Parse Search API results."""
        vendors = []
        organic = data.get("organic", [])
        
        for result in organic:
            # Extract domain
            link = result.get("link", "")
            domain = self._extract_domain(link)
            
            # Try to extract phone from snippet (regex-based)
            snippet = result.get("snippet", "")
            phone = self._extract_phone_from_text(snippet)
            
            vendors.append(VendorResult(
                name=result.get("title", ""),
                domain=domain,
                phone=phone,
                address=None,  # Not available in Search API
                rating=None,  # Not available
                rating_count=None,
                google_cid=None,
                latitude=None,
                longitude=None,
                categories=[],
                source_api="search"
            ))
        
        return vendors
    
    def parse_places_results(self, data: dict) -> List[VendorResult]:
        """Parse Places API results."""
        vendors = []
        places = data.get("places", [])
        
        for place in places:
            vendors.append(VendorResult(
                name=place.get("title", ""),
                domain=place.get("website"),
                phone=place.get("phoneNumber"),
                address=place.get("address"),
                rating=place.get("rating"),
                rating_count=place.get("ratingCount"),
                google_cid=place.get("cid"),
                latitude=place.get("latitude"),
                longitude=place.get("longitude"),
                categories=place.get("categories", []) or place.get("type", []),
                source_api="places"
            ))
        
        return vendors
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except:
            return None
    
    def _extract_phone_from_text(self, text: str) -> Optional[str]:
        """Extract phone number using regex."""
        import re
        pattern = r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def compare_results(self, query: str, num_results: int = 10) -> dict:
        """Compare Search API vs Places API for a single query."""
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}\n")
        
        # Test Search API
        print("Testing Search API...")
        search_result = self.search_api(query, num_results)
        search_vendors = self.parse_search_results(search_result["data"])
        
        print(f"  ✓ Search API: {len(search_vendors)} results in {search_result['elapsed_seconds']:.2f}s")
        
        # Test Places API
        print("Testing Places API...")
        places_result = self.places_api(query, num_results)
        places_vendors = self.parse_places_results(places_result["data"])
        
        print(f"  ✓ Places API: {len(places_vendors)} results in {places_result['elapsed_seconds']:.2f}s")
        
        # Analyze results
        analysis = {
            "query": query,
            "search_api": {
                "count": len(search_vendors),
                "elapsed_seconds": search_result["elapsed_seconds"],
                "vendors_with_phone": sum(1 for v in search_vendors if v.phone),
                "vendors_with_domain": sum(1 for v in search_vendors if v.domain),
                "vendors_with_rating": 0,
                "avg_rating": None,
                "vendors": [vars(v) for v in search_vendors]
            },
            "places_api": {
                "count": len(places_vendors),
                "elapsed_seconds": places_result["elapsed_seconds"],
                "vendors_with_phone": sum(1 for v in places_vendors if v.phone),
                "vendors_with_domain": sum(1 for v in places_vendors if v.domain),
                "vendors_with_rating": sum(1 for v in places_vendors if v.rating),
                "avg_rating": sum(v.rating for v in places_vendors if v.rating) / len([v for v in places_vendors if v.rating]) if any(v.rating for v in places_vendors) else None,
                "vendors": [vars(v) for v in places_vendors]
            }
        }
        
        return analysis
    
    def print_comparison_table(self, analysis: dict):
        """Print comparison results in a readable table."""
        print(f"\n{'='*80}")
        print("COMPARISON RESULTS")
        print(f"{'='*80}\n")
        
        print(f"{'Metric':<35} {'Search API':>20} {'Places API':>20}")
        print(f"{'-'*80}")
        
        search = analysis["search_api"]
        places = analysis["places_api"]
        
        print(f"{'Total Results':<35} {search['count']:>20} {places['count']:>20}")
        print(f"{'Response Time (seconds)':<35} {search['elapsed_seconds']:>20.2f} {places['elapsed_seconds']:>20.2f}")
        print(f"{'Vendors with Phone':<35} {search['vendors_with_phone']:>20} {places['vendors_with_phone']:>20}")
        print(f"{'Vendors with Domain':<35} {search['vendors_with_domain']:>20} {places['vendors_with_domain']:>20}")
        print(f"{'Vendors with Rating':<35} {search['vendors_with_rating']:>20} {places['vendors_with_rating']:>20}")
        
        if places['avg_rating']:
            print(f"{'Average Rating':<35} {'N/A':>20} {places['avg_rating']:>20.1f}")
        
        # Calculate percentages
        search_phone_pct = (search['vendors_with_phone'] / search['count'] * 100) if search['count'] > 0 else 0
        places_phone_pct = (places['vendors_with_phone'] / places['count'] * 100) if places['count'] > 0 else 0
        
        print(f"\n{'Data Quality Metrics':<35} {'Search API':>20} {'Places API':>20}")
        print(f"{'-'*80}")
        print(f"{'Phone Coverage %':<35} {search_phone_pct:>20.1f} {places_phone_pct:>20.1f}")
        
        print(f"\n{'='*80}\n")
    
    def run_comprehensive_test(self, queries: List[str]):
        """Run comparison across multiple queries."""
        all_analyses = []
        
        for query in queries:
            analysis = self.compare_results(query, num_results=10)
            all_analyses.append(analysis)
            self.print_comparison_table(analysis)
            
            # Small delay between queries
            time.sleep(1)
        
        # Save results
        output_file = "output_test/serper_api_comparison.json"
        os.makedirs("output_test", exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(all_analyses, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")
        
        return all_analyses


def main():
    """Run the API comparison test."""
    api_key = os.getenv("SERPER_API_KEY")
    
    if not api_key:
        print("❌ Error: SERPER_API_KEY not found in environment")
        return
    
    # Test queries representing different tender types
    test_queries = [
        "military uniforms manufacturers Texas",
        "ammunition suppliers Ontario Canada",
        "utility vehicle dealers Ontario",
        "IT consulting services Washington DC",
        "construction contractors California"
    ]
    
    print("="*80)
    print("SERPER API COMPARISON TEST")
    print("Search API vs Places API for Vendor Discovery")
    print("="*80)
    
    comparator = SerperAPIComparison(api_key)
    results = comparator.run_comprehensive_test(test_queries)
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY ACROSS ALL QUERIES")
    print("="*80 + "\n")
    
    total_search_vendors = sum(r["search_api"]["count"] for r in results)
    total_places_vendors = sum(r["places_api"]["count"] for r in results)
    total_search_with_phone = sum(r["search_api"]["vendors_with_phone"] for r in results)
    total_places_with_phone = sum(r["places_api"]["vendors_with_phone"] for r in results)
    
    avg_search_time = sum(r["search_api"]["elapsed_seconds"] for r in results) / len(results)
    avg_places_time = sum(r["places_api"]["elapsed_seconds"] for r in results) / len(results)
    
    print(f"Total Queries: {len(test_queries)}")
    print(f"Total Vendors Found (Search): {total_search_vendors}")
    print(f"Total Vendors Found (Places): {total_places_vendors}")
    print(f"Average Phone Coverage (Search): {total_search_with_phone / total_search_vendors * 100:.1f}%")
    print(f"Average Phone Coverage (Places): {total_places_with_phone / total_places_vendors * 100:.1f}%")
    print(f"Average Response Time (Search): {avg_search_time:.2f}s")
    print(f"Average Response Time (Places): {avg_places_time:.2f}s")
    
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80 + "\n")
    
    if total_places_with_phone > total_search_with_phone * 2:
        print("✅ Places API: Significantly better phone coverage")
    elif total_places_vendors > total_search_vendors * 1.2:
        print("✅ Places API: More vendors found")
    else:
        print("⚠️  Further analysis needed - results are comparable")


if __name__ == "__main__":
    main()
