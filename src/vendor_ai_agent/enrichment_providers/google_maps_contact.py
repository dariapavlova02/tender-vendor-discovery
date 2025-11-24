"""Google Maps Places API enrichment provider for phone numbers and website validation."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests

from ..database.connection import get_session
from ..database.models import APICache
from ..models import VendorRecord
from .base import BaseEnrichmentProvider


class GoogleMapsContactProvider(BaseEnrichmentProvider):
    
    TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        min_confidence: float = 0.7,
        cache_ttl_days: int = 90,
        timeout_seconds: int = 10
    ) -> None:
        super().__init__(name="google_maps_contact")
        self.api_key = api_key
        self.min_confidence = min_confidence
        self.cache_ttl_days = cache_ttl_days
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
    def enrich(self, vendor: VendorRecord) -> VendorRecord:
        if not self.api_key:
            self.logger.debug("Google Maps API key not configured, skipping enrichment")
            return vendor
        
        if self._should_skip_enrichment(vendor):
            return vendor
        
        self.logger.info(f"Google Maps enrichment for {vendor.company_name}")
        
        place_data = self._get_place_data(vendor)
        if not place_data:
            self.logger.debug(f"  No place data found for {vendor.company_name}")
            return vendor
        
        confidence = place_data.get("confidence", 0.0)
        if confidence < self.min_confidence:
            self.logger.debug(f"  Confidence {confidence:.2f} below threshold {self.min_confidence}")
            return vendor
        
        enrichment_applied = False
        
        phone = place_data.get("formatted_phone_number") or place_data.get("international_phone_number")
        if phone and not vendor.phone:
            vendor.phone = phone
            vendor.filtering_metadata["phone_source"] = "google_maps"
            vendor.filtering_metadata["phone_confidence"] = confidence
            enrichment_applied = True
            self.logger.info(f"  ✓ Phone: {phone}")
        
        website = place_data.get("website")
        if website and not vendor.website:
            vendor.website = website
            vendor.filtering_metadata["website_source"] = "google_maps"
            enrichment_applied = True
            self.logger.info(f"  ✓ Website: {website}")
        
        business_status = place_data.get("business_status")
        if business_status:
            vendor.filtering_metadata["business_status"] = business_status
            if business_status != "OPERATIONAL":
                self.logger.warning(f"  ⚠ Business status: {business_status}")
        
        rating = place_data.get("rating")
        user_ratings_total = place_data.get("user_ratings_total")
        if rating and user_ratings_total:
            vendor.filtering_metadata["google_rating"] = rating
            vendor.filtering_metadata["google_reviews_count"] = user_ratings_total
            self.logger.info(f"  ℹ Rating: {rating}/5 ({user_ratings_total} reviews)")
        
        if enrichment_applied:
            if "google_maps_enriched" not in vendor.enrichment_flags:
                vendor.enrichment_flags.append("google_maps_enriched")
        
        return vendor
    
    def _should_skip_enrichment(self, vendor: VendorRecord) -> bool:
        if self._has_real_phone(vendor):
            self.logger.debug(f"Vendor {vendor.company_name} already has real phone, skipping")
            return True
        
        if not vendor.company_name:
            self.logger.debug("Vendor has no company name, cannot search")
            return True
        
        return False
    
    def _has_real_phone(self, vendor: VendorRecord) -> bool:
        metadata = vendor.filtering_metadata
        return bool(
            vendor.phone and 
            vendor.phone != "N/A" and
            metadata.get("phone_source") not in [None, "fallback_static", "fallback_na"]
        )
    
    def _get_place_data(self, vendor: VendorRecord) -> Optional[dict]:
        cache_key = self._build_cache_key(vendor)
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            self.logger.debug(f"  Cache hit for {vendor.company_name}")
            return cached_data
        
        place_id = self._search_place(vendor)
        if not place_id:
            self._save_to_cache(cache_key, {})
            return None
        
        place_details = self._get_place_details(place_id)
        if not place_details:
            self._save_to_cache(cache_key, {})
            return None
        
        confidence = self._calculate_confidence(vendor, place_details)
        place_details["confidence"] = confidence
        
        self._save_to_cache(cache_key, place_details)
        return place_details
    
    def _search_place(self, vendor: VendorRecord) -> Optional[str]:
        query_parts = [vendor.company_name]
        
        if vendor.city:
            query_parts.append(vendor.city)
        if vendor.state:
            query_parts.append(vendor.state)
        if vendor.country:
            query_parts.append(vendor.country)
        
        query = ", ".join(query_parts)
        
        params = {
            "query": query,
            "key": self.api_key,
        }
        
        try:
            response = self.session.get(
                self.TEXT_SEARCH_URL,
                params=params,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            data = response.json()
            
            status = data.get("status")
            if status == "ZERO_RESULTS":
                self.logger.debug(f"  No results for: {query}")
                return None
            
            if status == "OVER_QUERY_LIMIT":
                self.logger.error("Google Maps API quota exceeded")
                return None
            
            if status != "OK":
                self.logger.warning(f"  API status: {status}")
                return None
            
            results = data.get("results", [])
            if not results:
                return None
            
            return results[0].get("place_id")
            
        except requests.RequestException as e:
            self.logger.error(f"Text search error: {e}")
            return None
    
    def _get_place_details(self, place_id: str) -> Optional[dict]:
        params = {
            "place_id": place_id,
            "fields": "formatted_phone_number,international_phone_number,website,business_status,rating,user_ratings_total,name,formatted_address",
            "key": self.api_key,
        }
        
        try:
            response = self.session.get(
                self.PLACE_DETAILS_URL,
                params=params,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            data = response.json()
            
            status = data.get("status")
            if status != "OK":
                self.logger.warning(f"  Place details status: {status}")
                return None
            
            result = data.get("result", {})
            return result
            
        except requests.RequestException as e:
            self.logger.error(f"Place details error: {e}")
            return None
    
    def _calculate_confidence(self, vendor: VendorRecord, place_data: dict) -> float:
        confidence = 0.0
        
        place_name = place_data.get("name", "").lower()
        vendor_name = vendor.company_name.lower()
        
        if place_name == vendor_name:
            confidence += 0.5
        elif place_name in vendor_name or vendor_name in place_name:
            confidence += 0.3
        else:
            common_words = set(place_name.split()) & set(vendor_name.split())
            if common_words:
                confidence += 0.2
        
        place_address = place_data.get("formatted_address", "").lower()
        
        if vendor.city and vendor.city.lower() in place_address:
            confidence += 0.2
        
        if vendor.state and vendor.state.lower() in place_address:
            confidence += 0.15
        
        if vendor.country and vendor.country.lower() in place_address:
            confidence += 0.1
        
        if vendor.postal_code and vendor.postal_code in place_address:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _build_cache_key(self, vendor: VendorRecord) -> str:
        key_parts = [
            vendor.company_name or "",
            vendor.city or "",
            vendor.state or "",
            vendor.country or "",
        ]
        key_string = "|".join(key_parts).lower()
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[dict]:
        try:
            with get_session() as session:
                cache_entry = session.query(APICache).filter(
                    APICache.source == "google_maps",
                    APICache.cache_key == cache_key,
                    APICache.expires_at > datetime.utcnow()
                ).first()
                
                if cache_entry:
                    return cache_entry.response_data
                
        except Exception as e:
            self.logger.warning(f"Cache read error: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, data: dict) -> None:
        try:
            with get_session() as session:
                expires_at = datetime.utcnow() + timedelta(days=self.cache_ttl_days)
                
                cache_entry = session.query(APICache).filter(
                    APICache.source == "google_maps",
                    APICache.cache_key == cache_key
                ).first()
                
                if cache_entry:
                    cache_entry.response_data = data
                    cache_entry.expires_at = expires_at
                else:
                    cache_entry = APICache(
                        source="google_maps",
                        cache_key=cache_key,
                        response_data=data,
                        expires_at=expires_at
                    )
                    session.add(cache_entry)
                
                session.commit()
                
        except Exception as e:
            self.logger.warning(f"Cache write error: {e}")
