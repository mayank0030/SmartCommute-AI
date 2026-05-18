"""Known traffic hotspots in Bengaluru with delay impacts."""
HOTSPOTS = [
    {"name": "Silk Board", "lat": 12.9178, "lng": 77.6227, "delay_min": 8, "radius_km": 1.0},
    {"name": "KR Puram", "lat": 12.9989, "lng": 77.7015, "delay_min": 6, "radius_km": 0.8},
    {"name": "Hebbal", "lat": 13.0358, "lng": 77.5970, "delay_min": 5, "radius_km": 0.7},
    {"name": "Tin Factory", "lat": 12.9900, "lng": 77.6640, "delay_min": 5, "radius_km": 0.6},
    {"name": "Marathahalli", "lat": 12.9591, "lng": 77.6974, "delay_min": 7, "radius_km": 0.9},
    {"name": "MG Road", "lat": 12.9756, "lng": 77.6066, "delay_min": 3, "radius_km": 0.5},
    {"name": "Majestic", "lat": 12.9767, "lng": 77.5713, "delay_min": 4, "radius_km": 0.5},
]


def get_traffic_delay(lat, lng, hour=None):
    """Calculate traffic delay at a given location and time."""
    import math
    delay = 0.0
    for h in HOTSPOTS:
        d = math.sqrt((lat - h["lat"]) ** 2 + (lng - h["lng"]) ** 2)
        if d * 111 <= h["radius_km"]:
            peak_factor = 1.0
            if hour is not None:
                if (7 <= hour <= 10) or (17 <= hour <= 20):
                    peak_factor = 1.5
                elif 22 <= hour or hour <= 5:
                    peak_factor = 0.3
            delay += h["delay_min"] * peak_factor * (1 - (d * 111) / h["radius_km"])
    return round(delay, 1)
