"""Walking time estimation for first/last mile."""
import math

WALKING_SPEED_KMH = 5.0

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def walk_time_minutes(lat1, lng1, lat2, lng2):
    dist = haversine_km(lat1, lng1, lat2, lng2)
    minutes = (dist / WALKING_SPEED_KMH) * 60
    return round(minutes, 1), round(dist, 3)

def find_nearest_stops(gtfs_loader, lat, lng, max_stops=3, max_radius_km=2.0):
    nearest = []
    for s in gtfs_loader.stops.values():
        dist = haversine_km(lat, lng, s["lat"], s["lng"])
        if dist <= max_radius_km:
            walk_min, _ = walk_time_minutes(lat, lng, s["lat"], s["lng"])
            nearest.append({"stopId": s["id"], "stopName": s["name"], "lat": s["lat"], "lng": s["lng"],
                            "distanceKm": round(dist, 2), "walkMinutes": walk_min})
    nearest.sort(key=lambda x: x["distanceKm"])
    return nearest[:max_stops]

def suggest_nearby_metro_stations(gtfs_loader, lat, lng):
    metro_keywords = ["metro", "metro station", "namma metro"]
    nearest = []
    for s in gtfs_loader.stops.values():
        name = s["name"].lower()
        if any(k in name for k in metro_keywords):
            dist = haversine_km(lat, lng, s["lat"], s["lng"])
            if dist <= 3.0:
                walk_min, _ = walk_time_minutes(lat, lng, s["lat"], s["lng"])
                nearest.append({"stopId": s["id"], "stopName": s["name"], "lat": s["lat"], "lng": s["lng"],
                                "distanceKm": round(dist, 2), "walkMinutes": walk_min})
    nearest.sort(key=lambda x: x["distanceKm"])
    return nearest[:2]
