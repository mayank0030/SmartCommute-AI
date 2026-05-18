import random
import math
import time
from traffic import get_traffic_delay, HOTSPOTS
from model import HistoricalDelayModel

DEFAULT_SPEED_KMH = 25
STOP_DWELL_SECONDS = 30


def interpolate_shape(shape_points, num_points=None):
    """Interpolate shape to get evenly spaced points."""
    if len(shape_points) < 2:
        return shape_points
    total_dist = 0.0
    segments = []
    for i in range(len(shape_points) - 1):
        d = math.sqrt(
            (shape_points[i + 1]["lat"] - shape_points[i]["lat"]) ** 2
            + (shape_points[i + 1]["lng"] - shape_points[i]["lng"]) ** 2
        ) * 111000
        total_dist += d
        segments.append(d)

    target = num_points or max(len(shape_points), total_dist // 50)
    if target < 2:
        return shape_points

    step = total_dist / (target - 1) if target > 1 else total_dist
    result = [shape_points[0]]
    accumulated = 0.0
    seg_idx = 0
    seg_progress = 0.0

    for _ in range(target - 2):
        while seg_idx < len(segments) and accumulated + segments[seg_idx] < (len(result)) * step:
            accumulated += segments[seg_idx]
            seg_idx += 1
            seg_progress = 0.0

        if seg_idx >= len(segments):
            break

        seg_progress += step
        fraction = min(seg_progress / segments[seg_idx], 1.0) if segments[seg_idx] > 0 else 1.0

        lat = shape_points[seg_idx]["lat"] + (shape_points[seg_idx + 1]["lat"] - shape_points[seg_idx]["lat"]) * fraction
        lng = shape_points[seg_idx]["lng"] + (shape_points[seg_idx + 1]["lng"] - shape_points[seg_idx]["lng"]) * fraction
        result.append({"lat": round(lat, 6), "lng": round(lng, 6)})

    result.append(shape_points[-1])
    return result


class Vehicle:
    def __init__(self, vehicle_id, route_id, shape_points, stops, schedule_time, route_name="", sim_hour=8):
        self.id = vehicle_id
        self.route_id = route_id
        self.route_name = route_name
        self.shape = interpolate_shape(shape_points, 100)
        self.stops = stops
        self.schedule_time = schedule_time
        self.sim_hour = sim_hour
        self.path_index = 0
        self.total_points = len(self.shape)
        self.speed_kmh = DEFAULT_SPEED_KMH
        self.on_time = True
        self.delay_minutes = 0.0
        self.occupancy = random.randint(20, 80)
        self.capacity = 80
        self.active = True
        self._route_characteristic = random.choice(["main_road", "highway", "inner_city"])

        if self.total_points > 0:
            self.lat = self.shape[0]["lat"]
            self.lng = self.shape[0]["lng"]
        else:
            self.lat = 12.97
            self.lng = 77.59

    def update(self, dt_seconds=2):
        if not self.active or self.path_index >= self.total_points - 1:
            return

        speed_ms = (self.speed_kmh * 1000) / 3600
        dist_per_step = speed_ms * dt_seconds
        dist_per_degree = 111000

        lat_per_step = dist_per_step / dist_per_degree

        while self.path_index < self.total_points - 1 and dist_per_step > 0:
            p1 = self.shape[self.path_index]
            p2 = self.shape[self.path_index + 1]

            seg_dist = math.sqrt((p2["lat"] - p1["lat"]) ** 2 + (p2["lng"] - p1["lng"]) ** 2) * dist_per_degree

            if seg_dist <= 0:
                self.path_index += 1
                continue

            ratio = dist_per_step / seg_dist
            if ratio >= 1.0:
                dist_per_step -= seg_dist
                self.path_index += 1
                if self.path_index >= self.total_points - 1:
                    break
            else:
                p1 = self.shape[self.path_index]
                p2 = self.shape[self.path_index + 1]
                self.lat = p1["lat"] + (p2["lat"] - p1["lat"]) * min(ratio, 1.0)
                self.lng = p1["lng"] + (p2["lng"] - p1["lng"]) * min(ratio, 1.0)
                dist_per_step = 0
                break

        if self.path_index >= self.total_points - 1:
            self.lat = self.shape[-1]["lat"]
            self.lng = self.shape[-1]["lng"]
            self.active = False
            return

        self.lat = round(self.lat, 6)
        self.lng = round(self.lng, 6)

        traffic_delay = get_traffic_delay(self.lat, self.lng, self.sim_hour)
        base_speed = DEFAULT_SPEED_KMH
        if self._route_characteristic == "highway":
            base_speed = 32
        elif self._route_characteristic == "inner_city":
            base_speed = 18

        if traffic_delay > 0:
            self.speed_kmh = max(6, base_speed - traffic_delay * 1.8)
            self.delay_minutes = traffic_delay * (1 + random.uniform(0, 0.3))
            self.on_time = False
        else:
            peak_factor = 1.0
            if (7 <= self.sim_hour <= 10) or (17 <= self.sim_hour <= 20):
                peak_factor = 0.8
            self.speed_kmh = base_speed * peak_factor + random.uniform(-2, 3)
            self.delay_minutes = max(0, self.delay_minutes * 0.95)
            if self.delay_minutes < 0.3:
                self.delay_minutes = 0
                self.on_time = True

        self.occupancy += random.randint(-5, 8)
        if (7 <= self.sim_hour <= 9) or (17 <= self.sim_hour <= 19):
            self.occupancy += random.randint(0, 5)
        self.occupancy = max(10, min(100, self.occupancy))

    def get_eta_to(self, target_lat, target_lng):
        remaining = 0.0
        found = False
        for i in range(self.path_index, self.total_points):
            p = self.shape[i]
            if not found and abs(p["lat"] - target_lat) < 0.001 and abs(p["lng"] - target_lng) < 0.001:
                found = True
                continue
            if found and i < self.total_points - 1:
                d = math.sqrt(
                    (self.shape[i + 1]["lat"] - p["lat"]) ** 2
                    + (self.shape[i + 1]["lng"] - p["lng"]) ** 2
                ) * 111000
                remaining += d

        if not found:
            for i in range(self.path_index, self.total_points):
                p = self.shape[i]
                if i < self.total_points - 1:
                    d = math.sqrt(
                        (self.shape[i + 1]["lat"] - p["lat"]) ** 2
                        + (self.shape[i + 1]["lng"] - p["lng"]) ** 2
                    ) * 111000
                    remaining += d

        speed_ms = max(2, (self.speed_kmh * 1000) / 3600)
        eta_seconds = remaining / speed_ms
        eta_minutes = eta_seconds / 60
        return round(eta_minutes + self.delay_minutes, 1)

    def to_dict(self):
        return {
            "id": self.id,
            "routeId": self.route_id,
            "routeName": self.route_name,
            "lat": self.lat,
            "lng": self.lng,
            "speed": round(self.speed_kmh, 1),
            "onTime": self.on_time,
            "delayMinutes": round(self.delay_minutes, 1),
            "occupancy": self.occupancy,
            "capacity": self.capacity,
            "active": self.active,
            "pathIndex": self.path_index,
            "totalPoints": self.total_points,
            "simHour": self.sim_hour,
        }


class SimulationEngine:
    def __init__(self, gtfs_loader):
        self.gtfs = gtfs_loader
        self.vehicles = {}
        self._vehicle_counter = 0
        self._time_of_day = 8.25
        self._running = False
        self.historical_model = HistoricalDelayModel()

    def _time_to_minutes(self, time_str):
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1])
        return h * 60 + m

    def seed_vehicles(self, route_ids=None, count_per_route=2):
        if route_ids is None:
            route_ids = list(self.gtfs.routes.keys())[:20]

        for rid in route_ids:
            route = self.gtfs.routes.get(rid)
            if not route:
                continue

            shape = self.gtfs.get_route_shape(rid)
            if not shape:
                continue

            stops = self.gtfs.get_route_stops(rid)
            if not stops:
                continue

            for i in range(count_per_route):
                vid = f"V{self._vehicle_counter:04d}"
                self._vehicle_counter += 1
                schedule_offset = i * 15
                vehicle = Vehicle(
                    vehicle_id=vid,
                    route_id=rid,
                    shape_points=shape,
                    stops=stops,
                    schedule_time=schedule_offset,
                    route_name=route.get("short_name") or route.get("long_name", "")[:30],
                    sim_hour=int(self._time_of_day),
                )
                vehicle.path_index = random.randint(0, max(0, vehicle.total_points - 10))
                p = vehicle.shape[vehicle.path_index]
                vehicle.lat = p["lat"]
                vehicle.lng = p["lng"]
                self.vehicles[vid] = vehicle

        return self

    def update_all(self, dt_seconds=2):
        self._time_of_day += dt_seconds / 3600
        if self._time_of_day > 24:
            self._time_of_day -= 24

        for v in self.vehicles.values():
            v.sim_hour = int(self._time_of_day)
            v.update(dt_seconds)

        self.historical_model.train_from_simulation(self.vehicles, self._time_of_day)

        expired = [vid for vid, v in self.vehicles.items() if not v.active]
        for vid in expired:
            v = self.vehicles[vid]
            self._respawn_vehicle(v)
            del self.vehicles[vid]

    def _respawn_vehicle(self, old_vehicle):
        vid = f"V{self._vehicle_counter:04d}"
        self._vehicle_counter += 1
        shape = self.gtfs.get_route_shape(old_vehicle.route_id)
        stops = self.gtfs.get_route_stops(old_vehicle.route_id)
        route = self.gtfs.routes.get(old_vehicle.route_id)
        if not shape or not stops:
            return
        vehicle = Vehicle(
            vehicle_id=vid,
            route_id=old_vehicle.route_id,
            shape_points=shape,
            stops=stops,
            schedule_time=old_vehicle.schedule_time + 20,
            route_name=old_vehicle.route_name,
            sim_hour=int(self._time_of_day),
        )
        vehicle.path_index = random.randint(0, min(5, vehicle.total_points - 1))
        p = vehicle.shape[vehicle.path_index]
        vehicle.lat = p["lat"]
        vehicle.lng = p["lng"]
        vehicle.sim_hour = int(self._time_of_day)
        self.vehicles[vid] = vehicle

    def get_vehicles_near(self, lat, lng, radius_km=2.0):
        results = []
        for v in self.vehicles.values():
            if not v.active:
                continue
            d = math.sqrt((v.lat - lat) ** 2 + (v.lng - lng) ** 2) * 111
            if d <= radius_km:
                results.append({"vehicle": v.to_dict(), "distance_km": round(d, 2)})
        results.sort(key=lambda x: x["distance_km"])
        return results

    def get_eta_to_stop(self, stop_lat, stop_lng):
        etas = []
        for v in self.vehicles.values():
            if not v.active:
                continue
            eta = v.get_eta_to(stop_lat, stop_lng)
            etas.append({"vehicle": v.to_dict(), "etaMinutes": eta})
        etas.sort(key=lambda x: x["etaMinutes"])
        return etas[:5]

    def get_state(self):
        return {
            "vehicles": [v.to_dict() for v in self.vehicles.values() if v.active],
            "activeCount": sum(1 for v in self.vehicles.values() if v.active),
            "timeOfDay": round(self._time_of_day, 2),
        }
