from typing import Optional, Tuple, Dict
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from functools import lru_cache
import time


class GeographicScorer:
    
    def __init__(self):
        self.geocoder = Nominatim(user_agent="vendor_ai_agent")
        self._cache = {}
    
    @lru_cache(maxsize=1000)
    def geocode_address(self, address: str, city: str, state: str, zip_code: str) -> Optional[Tuple[float, float]]:
        full_address = f"{address}, {city}, {state} {zip_code}, USA"
        
        if full_address in self._cache:
            return self._cache[full_address]
        
        try:
            time.sleep(1)
            location = self.geocoder.geocode(full_address, timeout=10)
            
            if location:
                coords = (location.latitude, location.longitude)
                self._cache[full_address] = coords
                return coords
            
            fallback = f"{city}, {state}, USA"
            location = self.geocoder.geocode(fallback, timeout=10)
            if location:
                coords = (location.latitude, location.longitude)
                self._cache[full_address] = coords
                return coords
                
        except Exception as e:
            print(f"Geocoding error for {full_address}: {e}")
        
        return None
    
    def calculate_distance_miles(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> float:
        return geodesic(origin, destination).miles
    
    def calculate_distance_score(
        self,
        distance_miles: float,
        max_distance: float = 3000.0
    ) -> float:
        if distance_miles <= 50:
            return 1.0
        elif distance_miles <= 200:
            return 0.9
        elif distance_miles <= 500:
            return 0.7
        elif distance_miles <= 1000:
            return 0.5
        elif distance_miles <= 2000:
            return 0.3
        elif distance_miles <= max_distance:
            return 0.1
        else:
            return 0.05
    
    def score_vendor_by_location(
        self,
        vendor_coords: Tuple[float, float],
        project_coords: Tuple[float, float]
    ) -> Dict[str, float]:
        distance = self.calculate_distance_miles(vendor_coords, project_coords)
        score = self.calculate_distance_score(distance)
        
        return {
            "distance_miles": round(distance, 2),
            "distance_score": score
        }
