"""Smart Departure Planner — delay propagation + what-if scenarios."""
import math
import random
from traffic import HOTSPOTS, get_traffic_delay
from prediction import get_model, get_scorer
from walking import find_nearest_stops
from routing import build_commute_options


def compute_delay_propagation(route_options, time_of_day):
    """
    For each route option, predict how delays will propagate.
    A bus that is 5 min from a traffic hotspot might face worse delay
    than one that is already past it.
    """
    enriched = []
    for opt in route_options:
        if opt["mode"] == "metro":
            enriched.append({**opt, "propagationNote": "Metro unaffected by road traffic", "propagationRisk": 0.0})
            continue

        delay = opt.get("totalDelayMinutes", 0) or opt.get("delayMinutes", 0)
        eta = opt["etaMinutes"]
        base = opt.get("baseRunningMinutes", eta)
        traffic_impact = opt.get("delayBreakdown", {}).get("trafficImpact", 0)

        peak = 1.0
        hour = int(time_of_day)
        if (7 <= hour <= 10) or (17 <= hour <= 20):
            peak = 1.4
        elif 22 <= hour or hour <= 5:
            peak = 0.4

        propagation = traffic_impact * peak * 0.3
        projected_delay = delay + propagation
        projected_eta = base + projected_delay

        note = ""
        risk = 0.0
        if propagation > 2:
            risk = min(0.9, propagation / 10)
            note = f"⚠️ Delay likely to worsen (+{propagation:.1f}min) — peak traffic building"
        elif propagation > 0.5:
            risk = 0.4
            note = f"⚠️ Slight delay increase possible (+{propagation:.1f}min)"
        else:
            risk = 0.1
            note = "✅ Delay stable — traffic not escalating"

        if opt.get("trafficNotes"):
            hotspot_names = [h for h in opt["trafficNotes"] if h != "historical adjustment"]
            if hotspot_names and propagation > 0.5:
                note += f" near {hotspot_names[0]}"

        enriched.append({
            **opt,
            "propagationMinutes": round(propagation, 1),
            "projectedDelayMinutes": round(projected_delay, 1),
            "projectedEtaMinutes": round(projected_eta, 1),
            "propagationNote": note,
            "propagationRisk": round(risk, 2),
        })
    return enriched


def departure_what_if(gtfs_loader, simulation_engine, user_lat, user_lng, dest_lat, dest_lng):
    """Generate what-if scenarios for leaving now vs waiting."""
    current_hour = simulation_engine._time_of_day
    raw_options = build_commute_options(gtfs_loader, simulation_engine, user_lat, user_lng, dest_lat, dest_lng)
    enriched = compute_delay_propagation(raw_options, current_hour)
    scorer = get_scorer()
    best_now = scorer.get_winner(enriched)

    scenarios = [{"delayMinutes": 0, "label": "Leave Now"}]

    for wait in [3, 5, 10]:
        future_hour = current_hour + wait / 60
        future_options = build_commute_options(gtfs_loader, simulation_engine, user_lat, user_lng, dest_lat, dest_lng)
        future_enriched = compute_delay_propagation(future_options, future_hour)
        future_best = scorer.get_winner(future_enriched)

        if future_best:
            scenarios.append({
                "delayMinutes": wait,
                "label": f"Wait {wait} min",
                "eta": future_best["etaMinutes"],
                "route": future_best["routeName"],
                "mode": future_best["mode"],
                "propagationNote": future_best.get("propagationNote", ""),
                "propagationRisk": future_best.get("propagationRisk", 0),
            })

    departure_score = 0
    if best_now:
        if best_now.get("propagationRisk", 0) > 0.5:
            departure_score = 1
        elif best_now.get("propagationRisk", 0) > 0.2:
            departure_score = 0
        else:
            departure_score = -1

    recommendation = ""
    if departure_score > 0:
        alt = next((s for s in scenarios if s["delayMinutes"] > 0), None)
        if alt:
            recommendation = (
                f"⚠️ Delay RISING on {best_now['routeName']}. "
                f"If you wait {alt['delayMinutes']}min, {alt['route']} "
                f"arrives in {alt['eta']}min instead."
            )
        else:
            recommendation = f"⚠️ Traffic building on {best_now['routeName']}. Consider leaving earlier."
    else:
        recommendation = (
            f"✅ {best_now['routeName']} is stable. "
            f"ETA {best_now['etaMinutes']}min. You have time to reach the stop."
        )

    return {
        "bestNow": best_now,
        "bestRoute": best_now["routeName"] if best_now else "",
        "bestEta": best_now["etaMinutes"] if best_now else 0,
        "recommendation": recommendation,
        "scenarios": scenarios,
        "allOptions": enriched,
        "peakHour": (7 <= int(current_hour) <= 10) or (17 <= int(current_hour) <= 20),
    }
