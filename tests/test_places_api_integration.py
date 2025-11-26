import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendor_ai_agent.enrichment_providers.serper_client import SerperClient
from vendor_ai_agent.sources.serper_search import SerperVendorSource
from vendor_ai_agent.models import TenderProfile, APIMetadata, PlaceOfPerformance
from vendor_ai_agent.config import RuntimeConfig

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_places_api_basic():
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.error("SERPER_API_KEY not found")
        return
    
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Basic Places API Call")
    logger.info("="*60)
    
    client = SerperClient(api_key=api_key)
    
    query = "military uniform manufacturer Virginia"
    logger.info(f"Query: {query}")
    
    response = client.places_search(query, num_results=5)
    places = response.get("places", [])
    
    logger.info(f"\nResults: {len(places)} places found")
    
    for idx, place in enumerate(places, 1):
        logger.info(f"\n[{idx}] {place.get('title', 'N/A')}")
        logger.info(f"  Phone: {place.get('phoneNumber', 'N/A')}")
        logger.info(f"  Rating: {place.get('rating', 'N/A')}")
        logger.info(f"  Address: {place.get('address', 'N/A')}")
        logger.info(f"  Website: {place.get('website', 'N/A')}")
        logger.info(f"  Coordinates: ({place.get('latitude', 'N/A')}, {place.get('longitude', 'N/A')})")
        logger.info(f"  CID: {place.get('cid', 'N/A')}")
    
    phone_count = sum(1 for p in places if p.get('phoneNumber'))
    rating_count = sum(1 for p in places if p.get('rating'))
    coords_count = sum(1 for p in places if p.get('latitude') and p.get('longitude'))
    
    logger.info(f"\nCoverage:")
    logger.info(f"  Phone: {phone_count}/{len(places)} ({phone_count/len(places)*100:.1f}%)")
    logger.info(f"  Rating: {rating_count}/{len(places)} ({rating_count/len(places)*100:.1f}%)")
    logger.info(f"  Coords: {coords_count}/{len(places)} ({coords_count/len(places)*100:.1f}%)")


def test_places_integration():
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.error("SERPER_API_KEY not found")
        return
    
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Full Integration with SerperVendorSource")
    logger.info("="*60)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    config.discovery.serper_use_places_api = True
    config.discovery.serper_discovery_query_limit = 3
    
    profile = TenderProfile(
        tender_id="TEST_PLACES_001",
        api_metadata=APIMetadata(
            place_of_performance=PlaceOfPerformance(
                city="Richmond",
                state_province="Virginia",
                country="USA"
            )
        )
    )
    
    source = SerperVendorSource(
        api_key=api_key,
        query_limit=3,
        results_per_query=5,
        config=config
    )
    
    vendors = source.search(profile)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"RESULTS SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total vendors: {len(vendors)}")
    
    with_phone = [v for v in vendors if v.phone]
    with_coords = [v for v in vendors if v.filtering_metadata.get('serper_latitude') and v.filtering_metadata.get('serper_longitude')]
    with_rating = [v for v in vendors if v.filtering_metadata.get('serper_rating')]
    
    logger.info(f"With phone: {len(with_phone)} ({len(with_phone)/len(vendors)*100:.1f}%)")
    logger.info(f"With coords: {len(with_coords)} ({len(with_coords)/len(vendors)*100:.1f}%)")
    logger.info(f"With rating: {len(with_rating)} ({len(with_rating)/len(vendors)*100:.1f}%)")
    
    logger.info(f"\nSample vendors:")
    for idx, vendor in enumerate(vendors[:5], 1):
        logger.info(f"\n[{idx}] {vendor.company_name}")
        logger.info(f"  Phone: {vendor.phone or 'N/A'}")
        logger.info(f"  Website: {vendor.website or 'N/A'}")
        logger.info(f"  Rating: {vendor.filtering_metadata.get('serper_rating', 'N/A')}")
        logger.info(f"  Coords: ({vendor.filtering_metadata.get('serper_latitude', 'N/A')}, {vendor.filtering_metadata.get('serper_longitude', 'N/A')})")


def test_places_vs_search_comparison():
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.error("SERPER_API_KEY not found")
        return
    
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Places API vs Search API Comparison")
    logger.info("="*60)
    
    config = RuntimeConfig()
    config.discovery.enable_serper_discovery = True
    config.discovery.serper_discovery_query_limit = 2
    config.discovery.serper_use_places_api = False
    
    profile = TenderProfile(
        tender_id="TEST_COMPARE_001",
        api_metadata=APIMetadata(
            place_of_performance=PlaceOfPerformance(
                city="Austin",
                state_province="Texas",
                country="USA"
            )
        )
    )
    
    source_search = SerperVendorSource(
        api_key=api_key,
        query_limit=2,
        results_per_query=5,
        config=config
    )
    
    logger.info("\n--- SEARCH API ---")
    vendors_search = source_search.search(profile)
    
    config.discovery.serper_use_places_api = True
    source_places = SerperVendorSource(
        api_key=api_key,
        query_limit=2,
        results_per_query=5,
        config=config
    )
    
    logger.info("\n--- PLACES API ---")
    vendors_places = source_places.search(profile)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"COMPARISON")
    logger.info(f"{'='*60}")
    logger.info(f"Search API: {len(vendors_search)} vendors")
    logger.info(f"Places API: {len(vendors_places)} vendors")
    
    search_phone = sum(1 for v in vendors_search if v.phone)
    places_phone = sum(1 for v in vendors_places if v.phone)
    
    search_coords = sum(1 for v in vendors_search if v.filtering_metadata.get('serper_latitude'))
    places_coords = sum(1 for v in vendors_places if v.filtering_metadata.get('serper_latitude'))
    
    logger.info(f"\nPhone coverage:")
    logger.info(f"  Search: {search_phone}/{len(vendors_search)} ({search_phone/max(len(vendors_search),1)*100:.1f}%)")
    logger.info(f"  Places: {places_phone}/{len(vendors_places)} ({places_phone/max(len(vendors_places),1)*100:.1f}%)")
    
    logger.info(f"\nCoordinate coverage:")
    logger.info(f"  Search: {search_coords}/{len(vendors_search)} ({search_coords/max(len(vendors_search),1)*100:.1f}%)")
    logger.info(f"  Places: {places_coords}/{len(vendors_places)} ({places_coords/max(len(vendors_places),1)*100:.1f}%)")


if __name__ == "__main__":
    test_places_api_basic()
    test_places_integration()
    test_places_vs_search_comparison()
    
    logger.info("\n" + "="*60)
    logger.info("ALL TESTS COMPLETED")
    logger.info("="*60)
