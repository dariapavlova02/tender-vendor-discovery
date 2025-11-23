import gzip
import os
import re
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

import requests
from requests.exceptions import Timeout, HTTPError
from sqlalchemy.orm import Session

from ..database import CacheManager, Vendor, VendorNAICS, get_session
from ..models import TenderProfile, VendorRecord, ContactInfo
from .base import BaseVendorSource


class SamEntitySource(BaseVendorSource):
    
    BASE_URL = "https://api.sam.gov/entity-information/v3/entities"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        use_cache: bool = True,
        cache_ttl_days: int = 7,
        rate_limit_per_day: int = 1000,
        sync_to_db: bool = True
    ):
        super().__init__(name="sam_entity")
        self.api_key = api_key or os.getenv("SAM_API_KEY")
        self.use_cache = use_cache
        self.cache_ttl_days = cache_ttl_days
        self.rate_limit_per_day = rate_limit_per_day
        self.sync_to_db = sync_to_db
        
        if not self.api_key:
            # raise ValueError("SAM_API_KEY is required for SamEntitySource")
            print("Warning: SAM_API_KEY not found. Running in offline/DB-only mode.")
        
        self.session = requests.Session()
        # self.session.headers.update({"X-Api-Key": self.api_key}) # API Key is passed as query param in V4
        
        self._request_count = 0
        self._request_window_start = datetime.utcnow()
    
    def is_compatible(self, profile: TenderProfile) -> bool:
        country = profile.dynamic_context.country if profile.dynamic_context else None
        
        if country == "Canada":
            return False
        
        naics_codes = profile.api_metadata.codes.naics or []
        if not naics_codes:
            return False
        
        return True
    
    def _check_rate_limit(self) -> None:
        now = datetime.utcnow()
        elapsed = (now - self._request_window_start).total_seconds()
        
        if elapsed >= 86400:
            self._request_count = 0
            self._request_window_start = now
        
        if self._request_count >= self.rate_limit_per_day:
            raise Exception(f"Rate limit exceeded: {self.rate_limit_per_day} requests/day")
    
    def _make_request(
        self,
        params: dict,
        cache_manager: Optional[CacheManager] = None
    ) -> dict:
        if cache_manager and self.use_cache:
            cached = cache_manager.get(params)
            if cached:
                return cached
        
        self._check_rate_limit()
        
        # API Key must be in query params
        if self.api_key:
            params["api_key"] = self.api_key
            
        url = f"{self.BASE_URL}?{urlencode(params)}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            self._request_count += 1
            
            data = response.json()
            
            if cache_manager and self.use_cache:
                cache_manager.set(params, data, self.cache_ttl_days)
            
            return data
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"SAM API request failed: {e}")
    
    def search_by_naics(
        self,
        naics_code: str,
        state: Optional[str] = None,
        limit: int = 10000,
        db_session: Optional[Session] = None,
        project_location: Optional[tuple] = None,
        sort_by_distance: bool = False
    ) -> List[dict]:
        print(f"Using SAM Extract API for NAICS {naics_code}...")
        
        params = {
            "naicsCode": naics_code,
            "includeSections": "entityRegistration,coreData,assertions",
            "format": "json"
        }
        
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.BASE_URL}?{urlencode(params)}"
        
        max_retries = 3
        retry_delays = [30, 60, 90]
        
        for attempt in range(max_retries):
            try:
                print(f"SAM Extract API request (attempt {attempt + 1}/{max_retries})...")
                response = self.session.get(url, timeout=120)
                response.raise_for_status()
                
                response_text = response.text.strip()
                
                url_match = re.search(r'https://[^\s]+', response_text)
                if not url_match:
                    raise Exception(f"No download URL found in response: {response_text[:200]}")
                
                download_url = url_match.group(0)
                print(f"Extract file URL received, downloading...")
                
                entities = self._download_and_parse_file(download_url)
                
                if state:
                    print(f"Filtering {len(entities)} entities by state: {state}")
                    filtered = []
                    for entity in entities:
                        physical_address = entity.get("coreData", {}).get("physicalAddress", {})
                        entity_state = physical_address.get("stateOrProvinceCode")
                        if entity_state == state:
                            filtered.append(entity)
                    print(f"Filtered to {len(filtered)} entities in {state}")
                    entities = filtered
                
                if sort_by_distance and project_location:
                    print(f"Scoring entities by distance (processing first {min(limit*5, len(entities))} for efficiency)...")
                    entities_to_score = entities[:limit*5]
                    scored_entities = self._score_and_sort_by_distance(entities_to_score, project_location)
                    return scored_entities[:limit]
                
                return entities[:limit]
                
            except (Timeout, HTTPError) as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"Request timeout/error: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"All retry attempts exhausted. Falling back to database...")
                    raise Exception(f"Extract API failed after {max_retries} attempts: {e}")
            except Exception as e:
                raise Exception(f"Extract API failed: {e}")
    


    def _download_and_parse_file(self, url: str) -> List[dict]:
        final_url = url
        if "REPLACE_WITH_API_KEY" in url and self.api_key:
            final_url = url.replace("REPLACE_WITH_API_KEY", self.api_key)
        
        max_retries = 10
        retry_delays = [5, 10, 15, 20, 30, 30, 30, 30, 30, 30]
        response = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(final_url, timeout=120)
                
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_code = error_data.get("errorCode", "")
                        
                        if error_code == "JSON_CSV_PENDING":
                            if attempt < max_retries - 1:
                                delay = retry_delays[attempt]
                                print(f"  File still generating, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                                time.sleep(delay)
                                continue
                            else:
                                raise Exception(f"File not ready after {max_retries} attempts ({sum(retry_delays[:max_retries])}s)")
                    except ValueError:
                        pass
                
                response.raise_for_status()
                
                content_type = response.headers.get("Content-Type", "")
                
                if "gzip" in content_type or not response.text.strip().startswith('{'):
                    print(f"  Decompressing gzip response ({len(response.content)} bytes)...")
                    decompressed = gzip.decompress(response.content)
                    import json
                    data = json.loads(decompressed.decode('utf-8'))
                else:
                    print(f"  Parsing JSON response...")
                    data = response.json()
                
                entities = data.get("entityData", [])
                print(f"  Successfully retrieved {len(entities)} entities")
                return entities
                
            except requests.exceptions.HTTPError as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    status_code = response.status_code if response else "unknown"
                    print(f"  HTTP error {status_code}, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    raise Exception(f"Failed to download file: {e}")
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"  Error occurred, retrying in {delay}s... (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(delay)
                else:
                    raise Exception(f"Failed to download file after {max_retries} attempts: {e}")
        
        return []
    
    def _parse_entity(self, entity_data: dict) -> Optional[Vendor]:
        try:
            core_data = entity_data.get("coreData", {})
            entity_reg = entity_data.get("entityRegistration", {})
            
            uei = entity_reg.get("ueiSAM")
            # duns = entity_reg.get("dunsNumber") # Removed in V3/V4
            cage_code = entity_reg.get("cageCode")
            legal_name = entity_reg.get("legalBusinessName", "")
            dba_name = entity_reg.get("dbaName")
            
            if not uei and not legal_name:
                return None
            
            physical_address = core_data.get("physicalAddress", {})
            
            business_types_data = core_data.get("businessTypes", {})
            business_type_list = business_types_data.get("businessTypeList", [])
            business_types = [bt.get("businessTypeDesc", "") for bt in business_type_list]
            
            # Extract website URL from entityInformation
            entity_info = core_data.get("entityInformation", {})
            website_url = entity_info.get("entityURL")
            
            vendor = Vendor(
                source=self.name,
                external_id=uei or cage_code,
                uei=uei,
                duns=None, # Deprecated
                cage_code=cage_code,
                legal_name=legal_name,
                dba_name=dba_name,
                website=website_url,
                country=physical_address.get("countryCode"),
                state=physical_address.get("stateOrProvinceCode"),
                city=physical_address.get("city"),
                address=physical_address.get("addressLine1"),
                postal_code=physical_address.get("zipCode"),
                business_types=business_types,
                is_small_business=any("Small" in bt for bt in business_types),
                is_woman_owned=any("Woman" in bt for bt in business_types),
                is_veteran_owned=any("Veteran" in bt for bt in business_types),
                is_minority_owned=any("Minority" in bt or "Disadvantaged" in bt for bt in business_types),
                is_8a=any("8(a)" in bt for bt in business_types),
                is_hubzone=any("HUBZone" in bt for bt in business_types),
                metadata_json=entity_data,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return vendor
            
        except Exception as e:
            print(f"Error parsing SAM entity: {e}")
            return None
    
    def _entity_to_vendor_record(self, entity_data: dict) -> Optional[VendorRecord]:
        vendor = self._parse_entity(entity_data)
        if not vendor:
            return None
        
        # Extract POC if available
        contact_info = None
        points_of_contact = entity_data.get("entityRegistration", {}).get("pointsOfContact", {})
        if points_of_contact:
            # Try to find a government business POC first, then fallback
            poc = points_of_contact.get("governmentBusinessPOC") or \
                  points_of_contact.get("electronicBusinessPOC") or \
                  points_of_contact.get("pastPerformancePOC")
            
            if poc:
                contact_info = ContactInfo(
                    name=f"{poc.get('firstName', '')} {poc.get('lastName', '')}".strip(),
                    email=poc.get("email"),
                    phone=poc.get("usPhone"),
                    organization=vendor.legal_name
                )

        business_types_list = []
        if vendor.business_types:
            if isinstance(vendor.business_types, list):
                business_types_list = vendor.business_types
            elif isinstance(vendor.business_types, str):
                business_types_list = [vendor.business_types]
        
        return VendorRecord(
            company_name=vendor.legal_name,
            website=vendor.website,
            email=contact_info.email if contact_info else None,
            phone=contact_info.phone if contact_info else None,
            location=f"{vendor.city}, {vendor.state}" if vendor.city and vendor.state else vendor.state,
            city=vendor.city,
            state=vendor.state,
            country=vendor.country,
            industry=None,
            source=self.name,
            is_past_winner=False,
            enrichment_flags=["sam_registered"],
            uei=vendor.uei,
            duns=vendor.duns,
            cage_code=vendor.cage_code,
            business_types=business_types_list,
            primary_contact=contact_info,
            total_contract_value=vendor.total_contract_value,
            contract_count=vendor.contract_count,
        )
    
    def search(self, profile: TenderProfile) -> List[VendorRecord]:
        naics_codes = profile.api_metadata.codes.naics or []
        if not naics_codes:
            return []
        
        vendors = []
        
        with get_session() as db_session:
            for naics_code in naics_codes[:3]:
                try:
                    state = None
                    if profile.country == "US":
                        state = profile.api_metadata.place_of_performance.state_province
                    
                    if self.api_key:
                        try:
                            entities = self.search_by_naics(
                                naics_code=naics_code,
                                state=state,
                                limit=50,
                                db_session=db_session
                            )
                            
                            for entity_data in entities:
                                if self.sync_to_db:
                                    vendor_obj = self._parse_entity(entity_data)
                                    if vendor_obj:
                                        existing = db_session.query(Vendor).filter(
                                            Vendor.source == self.name,
                                            Vendor.external_id == vendor_obj.external_id
                                        ).first()
                                        
                                        if existing:
                                            existing.updated_at = datetime.utcnow()
                                        else:
                                            db_session.add(vendor_obj)
                                            db_session.flush()
                                            
                                            assertions = entity_data.get("assertions", {})
                                            goods_services = assertions.get("goodsAndServices", {})
                                            naics_list = goods_services.get("naicsList", [])
                                            primary_naics = goods_services.get("primaryNaics", "")
                                            
                                            for naics_item in naics_list:
                                                naics_code = naics_item.get("naicsCode", "")
                                                naics_obj = VendorNAICS(
                                                    vendor_id=vendor_obj.id,
                                                    naics_code=naics_code,
                                                    naics_description=naics_item.get("naicsDescription"),
                                                    is_primary=(naics_code == primary_naics)
                                                )
                                                db_session.add(naics_obj)
                                        
                                        db_session.commit()
                                
                                vendor_record = self._entity_to_vendor_record(entity_data)
                                if vendor_record:
                                    vendors.append(vendor_record)
                        except Exception as e:
                            print(f"Error searching SAM API for NAICS {naics_code}: {e}")
                    
                    # Fallback or primary: Search DB
                    # If we didn't search API (no key) or even if we did, let's pull from DB to be sure we get everything
                    # especially if we are in offline mode.
                    
                    db_vendors = db_session.query(Vendor).join(VendorNAICS).filter(
                        Vendor.source == self.name,
                        VendorNAICS.naics_code == naics_code
                    )
                    
                    if state:
                        db_vendors = db_vendors.filter(Vendor.state == state)
                        
                    for db_vendor in db_vendors.limit(100).all():
                        # Convert DB vendor to VendorRecord
                        # We need a helper for this since _entity_to_vendor_record expects raw API JSON
                        # But we saved metadata_json, so we can use that OR map directly from DB fields
                        
                        # Mapping from DB fields is safer if metadata_json is missing (e.g. from CSV)
                        
                        contact = db_vendor.contacts[0] if db_vendor.contacts else None
                        primary_contact = None
                        if contact:
                            primary_contact = ContactInfo(
                                name=f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                                email=contact.email,
                                phone=contact.phone,
                                organization=db_vendor.legal_name
                            )

                        rec = VendorRecord(
                            company_name=db_vendor.legal_name,
                            website=db_vendor.website,
                            email=primary_contact.email if primary_contact else None,
                            phone=primary_contact.phone if primary_contact else None,
                            location=f"{db_vendor.city}, {db_vendor.state}" if db_vendor.city and db_vendor.state else db_vendor.state,
                            city=db_vendor.city,
                            state=db_vendor.state,
                            country=db_vendor.country,
                            industry=None, # Could derive from NAICS
                            source=self.name,
                            is_past_winner=False,
                            enrichment_flags=["sam_registered"],
                            uei=db_vendor.uei,
                            duns=db_vendor.duns,
                            cage_code=db_vendor.cage_code,
                            business_types=db_vendor.business_types if isinstance(db_vendor.business_types, list) else [],
                            primary_contact=primary_contact,
                            total_contract_value=db_vendor.total_contract_value,
                            contract_count=db_vendor.contract_count,
                        )
                        
                        # Avoid duplicates if we already got it from API in this run
                        if not any(v.company_name == rec.company_name for v in vendors):
                            vendors.append(rec)
                    
                    time.sleep(0.2)
                    
                except Exception as e:
                    print(f"Error searching SAM for NAICS {naics_code}: {e}")
                    continue
        
        return vendors[:100]

    def _score_and_sort_by_distance(
        self,
        entities: List[dict],
        project_location: tuple
    ) -> List[dict]:
        try:
            from ..modules.state_distance import estimate_distance_by_state, calculate_distance_score
        except:
            from geopy.distance import geodesic
            
            STATE_CENTERS = {"NM": (34.840515, -106.248482), "AZ": (33.729759, -111.431221), 
                           "TX": (31.054487, -97.563461), "CO": (39.059811, -105.311104),
                           "CA": (36.116203, -119.681564), "FL": (27.766279, -81.686783)}
            
            def estimate_distance_by_state(proj, state, city=None):
                if state not in STATE_CENTERS:
                    return 999999
                return round(geodesic(proj, STATE_CENTERS[state]).miles, 2)
            
            def calculate_distance_score(dist):
                if dist <= 50: return 1.0
                elif dist <= 200: return 0.9
                elif dist <= 500: return 0.7
                elif dist <= 1000: return 0.5
                elif dist <= 2000: return 0.3
                else: return 0.1
        
        scored_entities = []
        
        for entity in entities:
            physical_addr = entity.get("coreData", {}).get("physicalAddress", {})
            state = physical_addr.get("stateOrProvinceCode", "")
            city = physical_addr.get("city", "")
            
            if not state:
                entity["_distance_miles"] = 999999
                entity["_distance_score"] = 0.0
            else:
                distance = estimate_distance_by_state(project_location, state, city)
                score = calculate_distance_score(distance)
                entity["_distance_miles"] = distance
                entity["_distance_score"] = score
            
            scored_entities.append(entity)
        
        scored_entities.sort(key=lambda x: x.get("_distance_miles", 999999))
        
        print(f"Distance scoring complete (state-level estimation). Top 5:")
        for i, entity in enumerate(scored_entities[:5]):
            distance = entity.get("_distance_miles", "N/A")
            score = entity.get("_distance_score", "N/A")
            city = entity.get("coreData", {}).get("physicalAddress", {}).get("city", "Unknown")
            state = entity.get("coreData", {}).get("physicalAddress", {}).get("stateOrProvinceCode", "")
            print(f"  #{i+1}: {city}, {state} - {distance} mi (score: {score})")
        
        return scored_entities
