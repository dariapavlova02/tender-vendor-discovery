from typing import Dict, Tuple


STATE_CENTERS = {
    "AL": (32.806671, -86.791130),
    "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221),
    "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564),
    "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371),
    "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783),
    "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337),
    "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137),
    "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526),
    "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067),
    "LA": (31.169546, -91.867805),
    "ME": (44.693947, -69.381927),
    "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106),
    "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192),
    "MS": (32.741646, -89.678696),
    "MO": (38.456085, -92.288368),
    "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082),
    "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896),
    "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482),
    "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419),
    "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915),
    "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938),
    "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.511780),
    "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828),
    "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461),
    "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686),
    "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494),
    "WV": (38.491226, -80.954456),
    "WI": (44.268543, -89.616508),
    "WY": (42.755966, -107.302490),
    "DC": (38.907192, -77.036873),
    "PR": (18.220833, -66.590149),
}


CITY_COORDS = {
    ("ALBUQUERQUE", "NM"): (35.0844, -106.6504),
    ("LAS CRUCES", "NM"): (32.3199, -106.7637),
    ("HOBBS", "NM"): (32.7026, -103.1360),
    ("SANTA FE", "NM"): (35.6870, -105.9378),
    ("RIO RANCHO", "NM"): (35.2334, -106.6630),
    ("ROSWELL", "NM"): (33.3943, -104.5230),
    ("FARMINGTON", "NM"): (36.7280, -108.2187),
    ("CLOVIS", "NM"): (34.4048, -103.2052),
    ("ALAMOGORDO", "NM"): (32.8995, -105.9603),
    ("CARLSBAD", "NM"): (32.4207, -104.2288),
    ("GALLUP", "NM"): (35.5281, -108.7426),
    ("LOS ALAMOS", "NM"): (35.8892, -106.3058),
    ("ARTESIA", "NM"): (32.8423, -104.4033),
    ("PORTALES", "NM"): (34.1862, -103.3338),
    ("SILVER CITY", "NM"): (32.7701, -108.2803),
}


def estimate_distance_by_state(
    project_coords: Tuple[float, float], 
    vendor_state: str, 
    vendor_city: str | None = None
) -> float:
    from geopy.distance import geodesic
    
    if vendor_city and vendor_state:
        city_key = (vendor_city.upper().strip(), vendor_state.upper().strip())
        if city_key in CITY_COORDS:
            city_coords = CITY_COORDS[city_key]
            distance = geodesic(project_coords, city_coords).miles
            return round(distance, 2)
    
    if vendor_state not in STATE_CENTERS:
        return 999999
    
    state_center = STATE_CENTERS[vendor_state]
    distance = geodesic(project_coords, state_center).miles
    return round(distance, 2)


def calculate_distance_score(distance_miles: float) -> float:
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
    else:
        return 0.1
