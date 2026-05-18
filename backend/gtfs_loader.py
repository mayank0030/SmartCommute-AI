import csv
import os
import math
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "bengaluru", "gtfs")
ZIP_PATH = os.path.join(os.path.dirname(__file__), "data", "bengaluru", "bmtc-gtfs.zip")


def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        _extract_gtfs()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _extract_gtfs():
    import zipfile
    if not os.path.exists(ZIP_PATH):
        print(f"GTFS zip not found at {ZIP_PATH}")
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(DATA_DIR)
    print(f"Extracted GTFS data to {DATA_DIR}")


def haversine(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class GTFSLoader:
    def __init__(self):
        self.routes = {}
        self.stops = {}
        self.trips = {}
        self.stop_times = defaultdict(list)
        self.shapes = defaultdict(list)
        self.route_trips = defaultdict(list)
        self.route_shapes = defaultdict(set)

    def load(self):
        routes_data = load_csv("routes.txt")
        for r in routes_data:
            rid = r["route_id"]
            self.routes[rid] = {
                "id": rid,
                "short_name": r.get("route_short_name", ""),
                "long_name": r.get("route_long_name", ""),
                "type": int(r.get("route_type", 3)),
            }

        stops_data = load_csv("stops.txt")
        for s in stops_data:
            sid = s["stop_id"]
            self.stops[sid] = {
                "id": sid,
                "name": s.get("stop_name", ""),
                "lat": float(s.get("stop_lat", 0)),
                "lng": float(s.get("stop_lon", 0)),
            }

        trips_data = load_csv("trips.txt")
        for t in trips_data:
            tid = t["trip_id"]
            rid = t["route_id"]
            self.trips[tid] = {
                "id": tid,
                "route_id": rid,
                "shape_id": t.get("shape_id", ""),
                "direction": int(t.get("direction_id", 0)),
            }
            self.route_trips[rid].append(tid)
            if t.get("shape_id"):
                self.route_shapes[rid].add(t["shape_id"])

        stop_times_data = load_csv("stop_times.txt")
        for st in stop_times_data:
            tid = st["trip_id"]
            self.stop_times[tid].append({
                "stop_id": st["stop_id"],
                "stop_sequence": int(st.get("stop_sequence", 0)),
                "arrival_time": st.get("arrival_time", ""),
                "departure_time": st.get("departure_time", ""),
            })

        shapes_data = load_csv("shapes.txt")
        for sh in shapes_data:
            sid = sh["shape_id"]
            self.shapes[sid].append({
                "lat": float(sh["shape_pt_lat"]),
                "lng": float(sh["shape_pt_lon"]),
                "seq": int(sh["shape_pt_sequence"]),
            })

        for sid in self.shapes:
            self.shapes[sid].sort(key=lambda x: x["seq"])

        return self

    def get_route_stops(self, route_id):
        all_stops = []
        seen = set()
        for tid in self.route_trips.get(route_id, []):
            for st in self.stop_times.get(tid, []):
                if st["stop_id"] not in seen:
                    seen.add(st["stop_id"])
                    stop = self.stops.get(st["stop_id"])
                    if stop:
                        all_stops.append({**stop, "sequence": st["stop_sequence"]})
        all_stops.sort(key=lambda x: x["sequence"])
        return all_stops

    def get_route_shape(self, route_id):
        for sid in self.route_shapes.get(route_id, set()):
            if sid in self.shapes:
                return self.shapes[sid]
        return []

    def find_routes_near(self, lat, lng, radius_km=1.0):
        nearby = []
        for rid, route in self.routes.items():
            stops = self.get_route_stops(rid)
            for s in stops[:3]:
                d = haversine(lat, lng, s["lat"], s["lng"])
                if d <= radius_km:
                    nearby.append({"route": route, "distance_km": round(d, 2), "nearest_stop": s["name"]})
                    break
        nearby.sort(key=lambda x: x["distance_km"])
        return nearby[:10]

    def get_all_routes(self):
        return list(self.routes.values())

    def get_shape_coords(self, shape_id):
        return [{"lat": p["lat"], "lng": p["lng"]} for p in self.shapes.get(shape_id, [])]
