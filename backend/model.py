"""Deep prediction model: statistical, multi-factor ETA with learned patterns."""
import math
import random
import statistics
from collections import defaultdict
from traffic import HOTSPOTS, get_traffic_delay


class HistoricalDelayModel:
    """
    Learns delay patterns per route per hour from observations.
    Uses exponential moving average so recent observations weigh more.
    """
    def __init__(self, decay_factor=0.3):
        self._data = defaultdict(lambda: defaultdict(list))
        self._averages = defaultdict(dict)
        self._decay = decay_factor

    def observe(self, route_id, hour, delay_minutes):
        self._data[route_id][hour].append(delay_minutes)
        if len(self._data[route_id][hour]) > 100:
            self._data[route_id][hour] = self._data[route_id][hour][-100:]
        old = self._averages[route_id].get(hour, delay_minutes)
        self._averages[route_id][hour] = old * (1 - self._decay) + delay_minutes * self._decay

    def predict_delay(self, route_id, hour):
        avg = self._averages.get(route_id, {}).get(hour)
        if avg is not None:
            return round(avg, 1)
        samples = self._data.get(route_id, {}).get(hour, [])
        if samples:
            return round(statistics.mean(samples), 1)
        return 0.0

    def get_variance(self, route_id, hour):
        samples = self._data.get(route_id, {}).get(hour, [])
        if len(samples) >= 3:
            return round(statistics.stdev(samples), 2)
        return 2.0

    def save(self, filepath="historical_delays.json"):
        import json
        data = {}
        for rid, hours in self._averages.items():
            data[rid] = {str(h): v for h, v in hours.items()}
        with open(filepath, "w") as f:
            json.dump(data, f)

    def load(self, filepath="historical_delays.json"):
        import json, os
        if not os.path.exists(filepath):
            return
        with open(filepath) as f:
            data = json.load(f)
        for rid, hours in data.items():
            for h, v in hours.items():
                self._averages[rid][int(h)] = v

    def train_from_simulation(self, vehicles, time_of_day):
        """Feed observations from active vehicles into the model."""
        for v in vehicles.values():
            if not v.active:
                continue
            hour = int(time_of_day)
            self.observe(v.route_id, hour, v.delay_minutes)


class TrafficPropagationModel:
    """
    Predicts how traffic ahead affects the remaining journey.
    Instead of just checking current traffic, it looks at every hotspot
    between the vehicle's position and the destination.
    """
    def __init__(self):
        self.hotspots = HOTSPOTS

    def compute_route_traffic_impact(self, vehicle_lat, vehicle_lng, dest_lat, dest_lng, hour):
        total_impact = 0.0
        hotspots_hit = []

        for h in self.hotspots:
            d_h = math.sqrt((h["lat"] - vehicle_lat)**2 + (h["lng"] - vehicle_lng)**2) * 111
            d_dest = math.sqrt((h["lat"] - dest_lat)**2 + (h["lng"] - dest_lng)**2) * 111

            if d_h <= 3.0 and d_dest <= d_h:
                peak = self._peak_factor(hour)
                severity = h["delay_min"] * peak
                proximity = max(0, 1 - d_h / 3.0)
                impact = severity * proximity * 0.7
                total_impact += impact
                if impact > 0.5:
                    hotspots_hit.append(h["name"])

        current_traffic = get_traffic_delay(vehicle_lat, vehicle_lng, hour)
        total_impact += current_traffic * 0.4

        return round(total_impact, 1), hotspots_hit

    def _peak_factor(self, hour):
        if hour is None:
            return 1.0
        if (7 <= hour <= 10) or (17 <= hour <= 20):
            return 1.5 + random.uniform(0, 0.3)
        if 22 <= hour or hour <= 5:
            return 0.3
        return 0.7


class StopDwellModel:
    """
    Estimates time a bus spends at stops based on occupancy and time.
    Higher occupancy = longer dwell. Peak hours = longer dwell.
    """
    def estimate_dwell(self, occupancy_pct, hour, stop_count):
        base_dwell = 12
        occ_factor = 1 + (occupancy_pct / 100) * 0.5
        peak_factor = 1.0
        if hour is not None:
            if (7 <= hour <= 10) or (17 <= hour <= 20):
                peak_factor = 1.3
        dwell_per_stop = base_dwell * occ_factor * peak_factor
        return round(dwell_per_stop * stop_count / 60, 1)

    def confidence(self, occupancy_pct, stop_count):
        if stop_count == 0:
            return 0.5
        return min(1.0, (1 - occupancy_pct / 150) * (1 - 1 / (stop_count + 1)))


class MultiFactorETAModel:
    """
    Combines all factors into a single ETA prediction with confidence bounds.
    ETA = base_running_time + traffic_impact + historical_adjustment
          + stop_dwell + stochastic_noise
    """
    def __init__(self):
        self.historical = HistoricalDelayModel()
        self.traffic_propagation = TrafficPropagationModel()
        self.stop_dwell = StopDwellModel()

    def predict(self, vehicle_state, dest_lat, dest_lng, hour=None, stop_count=0):
        lat = vehicle_state.get("lat", 0)
        lng = vehicle_state.get("lng", 0)
        speed = vehicle_state.get("speed", 25)
        delay = vehicle_state.get("delayMinutes", 0)
        route_id = vehicle_state.get("routeId", "")
        occupancy = vehicle_state.get("occupancy", 50)

        if hour is None:
            hour = int(vehicle_state.get("simHour", 8))

        dist = math.sqrt((lat - dest_lat)**2 + (lng - dest_lng)**2) * 111
        base_running = (dist / max(speed, 1)) * 60

        traffic_impact, hotspots_hit = self.traffic_propagation.compute_route_traffic_impact(
            lat, lng, dest_lat, dest_lng, hour
        )

        historical_adjust = self.historical.predict_delay(route_id, hour)
        variance = self.historical.get_variance(route_id, hour)

        dwell = self.stop_dwell.estimate_dwell(occupancy, hour, stop_count)

        stochastic_noise = random.gauss(0, 0.3)

        total_delay = traffic_impact + historical_adjust + dwell + delay
        eta = base_running + total_delay + stochastic_noise
        eta = max(0.5, eta)

        lower_bound = max(0.5, eta - variance * 0.5)
        upper_bound = eta + variance * 1.2

        if variance < 1.0:
            confidence = "high"
            conf_score = 0.9
        elif variance < 2.5:
            confidence = "medium"
            conf_score = 0.65
        else:
            confidence = "low"
            conf_score = 0.4

        if eta > 30:
            confidence = "low"
            conf_score = min(conf_score, 0.35)

        reliability = round(max(0, 1 - (total_delay / max(eta, 1)) * 0.5), 2)

        return {
            "etaMinutes": round(eta, 1),
            "etaRange": [round(lower_bound, 1), round(upper_bound, 1)],
            "baseRunningMinutes": round(base_running, 1),
            "totalDelayMinutes": round(total_delay, 1),
            "delayBreakdown": {
                "trafficImpact": round(traffic_impact, 1),
                "historicalAdjustment": round(historical_adjust, 1),
                "stopDwellMinutes": round(dwell, 1),
                "currentBusDelay": round(delay, 1),
            },
            "trafficHotspots": hotspots_hit,
            "speedKmph": round(speed, 1),
            "distanceKm": round(dist, 2),
            "confidence": confidence,
            "confidenceScore": conf_score,
            "reliability": reliability,
            "variance": variance,
        }


class RouteScorer:
    """
    Advanced route comparison with multi-factor scoring.
    Score = eta_weight * eta + delay_weight * delay + reliability_penalty
            + mode_preference + occupancy_penalty
    """
    def __init__(self):
        self.weights = {
            "eta": 1.0,
            "delay": 1.8,
            "reliability": 3.0,
            "mode_penalty": {"bus": 2.0, "metro": 1.0},
            "occupancy_threshold": 85,
        }

    def score_route(self, route):
        eta = route.get("etaMinutes", 999)
        delay = route.get("delayMinutes", 0) or route.get("totalDelayMinutes", 0)
        mode = route.get("mode", "bus")
        reliability = route.get("reliability", 0.5)
        occupancy_str = route.get("occupancy", "0%")
        occupancy = int(occupancy_str.replace("%", "")) if isinstance(occupancy_str, str) else occupancy_str

        eta_score = self.weights["eta"] * eta
        delay_score = self.weights["delay"] * delay
        reliability_penalty = self.weights["reliability"] * (1 - reliability)
        mode_penalty = self.weights["mode_penalty"].get(mode, 2.0)
        occ_penalty = 2.0 if occupancy > self.weights["occupancy_threshold"] else 0.0

        total = eta_score + delay_score + reliability_penalty + mode_penalty + occ_penalty
        return round(total, 1)

    def rank(self, routes):
        scored = []
        for r in routes:
            s = self.score_route(r)
            scored.append({**r, "score": s})
        scored.sort(key=lambda x: x["score"])
        return scored

    def get_winner(self, routes):
        ranked = self.rank(routes)
        return ranked[0] if ranked else None


def explain_prediction(eta_result):
    """Generate a human-readable explanation of the ETA prediction."""
    lines = []
    eta = eta_result["etaMinutes"]
    delay = eta_result["totalDelayMinutes"]
    breakdown = eta_result["delayBreakdown"]
    confidence = eta_result["confidence"]
    hotspots = eta_result["trafficHotspots"]

    lines.append(f"ETA: {eta} min ({confidence} confidence)")
    lines.append(f"Range: {eta_result['etaRange'][0]}-{eta_result['etaRange'][1]} min")

    if delay > 0:
        reasons = []
        if breakdown["trafficImpact"] > 0.5:
            reasons.append(f"traffic ({breakdown['trafficImpact']}min)")
        if breakdown["historicalAdjustment"] > 0.5:
            reasons.append(f"historical pattern ({breakdown['historicalAdjustment']}min)")
        if breakdown["stopDwellMinutes"] > 0.5:
            reasons.append(f"stop dwell ({breakdown['stopDwellMinutes']}min)")
        if breakdown["currentBusDelay"] > 0.5:
            reasons.append(f"current bus delay ({breakdown['currentBusDelay']}min)")
        lines.append(f"Delays: {', '.join(reasons)}")

    if hotspots:
        lines.append(f"Traffic hotspots ahead: {', '.join(hotspots)}")

    return "; ".join(lines)
