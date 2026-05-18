"""Prediction layer using the deep multi-factor ETA model."""
from model import MultiFactorETAModel, RouteScorer, explain_prediction

_model = MultiFactorETAModel()
_scorer = RouteScorer()


def predict_eta(vehicle_state, target_lat, target_lng, stop_count=0, target_stop_name=""):
    result = _model.predict(
        vehicle_state,
        target_lat,
        target_lng,
        hour=vehicle_state.get("simHour"),
        stop_count=stop_count,
    )
    result["targetStop"] = target_stop_name
    result["explanation"] = explain_prediction(result)
    return result


def compare_routes(routes_with_etas):
    ranked = _scorer.rank(routes_with_etas)
    return ranked


def get_model():
    return _model


def get_scorer():
    return _scorer


def format_route_suggestion(route, index=0):
    prefix = "Suggested" if index == 0 else f"Option {index + 1}"
    icon = "[Bus]" if route.get("mode") == "bus" else "[Metro]"
    delay_str = ""
    total = route.get("totalDelayMinutes", 0) or route.get("delayMinutes", 0)
    if total > 1:
        delay_str = f" | +{total}min delay"
    eta_str = f"{route.get('etaMinutes', '?')} min"
    conf = route.get("confidence", "")
    return f"{icon} {route.get('routeName', 'Route')} - {eta_str}{delay_str} [{conf}]"
