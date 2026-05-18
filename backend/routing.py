"""Route optimization using deep prediction model with walk times."""
import math
from traffic import HOTSPOTS
from prediction import predict_eta, compare_routes, get_scorer
from walking import find_nearest_stops, suggest_nearby_metro_stations


def build_commute_options(gtfs_loader, simulation_engine, user_lat, user_lng, dest_lat, dest_lng):
    nearby = simulation_engine.get_vehicles_near(user_lat, user_lng, radius_km=5.0)
    route_options = []

    for entry in nearby[:6]:
        v = entry["vehicle"]
        route = gtfs_loader.routes.get(v["routeId"])
        route_name = v.get("routeName", "") or (route.get("short_name", "") if route else "")

        stop_count = 0
        if route:
            stops = gtfs_loader.get_route_stops(route["id"])
            total_stops = len(stops)
            progress = v.get("pathIndex", 0) / max(v.get("totalPoints", 1), 1)
            remaining_stops = max(1, int(total_stops * (1 - progress)))
            stop_count = min(remaining_stops, 6)

        eta_result = predict_eta(v, dest_lat, dest_lng, stop_count=stop_count)

        nearest_stops = find_nearest_stops(gtfs_loader, user_lat, user_lng, max_stops=1, max_radius_km=3.0)
        wlk_min = nearest_stops[0]["walkMinutes"] if nearest_stops else 5.0

        traffic_notes = []
        for h in HOTSPOTS:
            d = math.sqrt((v["lat"] - h["lat"]) ** 2 + (v["lng"] - h["lng"]) ** 2) * 111
            if d <= 2.0:
                traffic_notes.append(h["name"])

        route_options.append({
            "routeId": v["routeId"],
            "routeName": route_name or f"Route {v['routeId']}",
            "mode": "bus",
            "etaMinutes": eta_result["etaMinutes"],
            "etaRange": eta_result["etaRange"],
            "delayMinutes": round(eta_result["totalDelayMinutes"], 1),
            "totalDelayMinutes": round(eta_result["totalDelayMinutes"], 1),
            "delayBreakdown": eta_result["delayBreakdown"],
            "walkMinutes": wlk_min,
            "distanceKm": round(entry["distance_km"], 2),
            "trafficNotes": list(set(traffic_notes + eta_result["trafficHotspots"])),
            "vehicleId": v["id"],
            "occupancy": f"{v.get('occupancy', 0)}%",
            "confidence": eta_result["confidence"],
            "confidenceScore": eta_result["confidenceScore"],
            "reliability": eta_result["reliability"],
            "variance": eta_result["variance"],
            "baseRunningMinutes": eta_result["baseRunningMinutes"],
        })

    metro_option = {
        "routeId": "metro_purple",
        "routeName": "Metro Purple Line",
        "mode": "metro",
        "etaMinutes": 14.0,
        "etaRange": [12.0, 16.0],
        "delayMinutes": 1.0,
        "totalDelayMinutes": 1.0,
        "delayBreakdown": {"trafficImpact": 0, "historicalAdjustment": 0.5, "stopDwellMinutes": 0.5, "currentBusDelay": 0},
        "walkMinutes": 8.0,
        "distanceKm": 0.0,
        "trafficNotes": [],
        "vehicleId": "",
        "occupancy": "65%",
        "confidence": "high",
        "confidenceScore": 0.9,
        "reliability": 0.92,
        "variance": 0.8,
        "baseRunningMinutes": 12.0,
    }

    metro_stations = suggest_nearby_metro_stations(gtfs_loader, user_lat, user_lng)
    if metro_stations:
        nearest_metro = metro_stations[0]
        metro_option["walkMinutes"] = nearest_metro["walkMinutes"]
        metro_option["routeName"] = f"Metro via {nearest_metro['stopName']}"
        metro_option["distanceKm"] = nearest_metro["distanceKm"]
        metro_option["etaMinutes"] = round(nearest_metro["walkMinutes"] + 12.0, 1)

    route_options.append(metro_option)

    ranked = compare_routes(route_options)
    return ranked


def get_best_option(route_options):
    return get_scorer().get_winner(route_options)
