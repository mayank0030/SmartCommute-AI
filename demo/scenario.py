"""End-to-end demo: Priya's Morning Commute (Deep Model)"""
import requests, json, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API = "http://127.0.0.1:8000"

def print_header(text):
    print(f"\n{'='*55}")
    print(f"  {text}")
    print(f"{'='*55}")

def fetch(endpoint, params=None):
    url = f"{API}/{endpoint}"
    r = requests.get(url, params=params, timeout=10)
    return r.json()

def demo_scenario():
    print_header("PRIYA'S MORNING COMMUTE - BENGALURU (DEEP MODEL)")
    print("""
  Priya lives in Koramangala and works near MG Road.
  Her bus (route 14A) is scheduled at 8:22 AM.
  But she never knows if it will arrive on time, early, or late.

  The Smart Commute Assistant uses a multi-factor prediction model:
  - Base running time (distance / speed)
  - Traffic propagation (hotspots along remaining route)
  - Historical delay patterns (per-route, per-hour)
  - Stop dwell estimation (occupancy-based)
  - Confidence bounds (statistical variance)
  """)

    demo = fetch("demo")
    print(f"  From: {demo['from']['name']}")
    print(f"  To:   {demo['to']['name']}")

    print_header("STEP 1: LIVE FLEET STATUS")
    vehicles = fetch("vehicles")
    delayed = [v for v in vehicles['vehicles'] if not v['onTime']]
    print(f"\n  Active buses: {vehicles['activeCount']}")
    print(f"  On time: {vehicles['activeCount'] - len(delayed)}")
    print(f"  Delayed: {len(delayed)}")
    for v in delayed[:3]:
        print(f"    {v['routeName']} - {v['delayMinutes']}min delay at ({v['lat']:.3f}, {v['lng']:.3f})")

    print_header("STEP 2: PREDICTION ENGINE ANALYSIS")
    f = demo['from']
    t = demo['to']
    commute = fetch("commute", {"from_lat": f["lat"], "from_lng": f["lng"],
                                "to_lat": t["lat"], "to_lng": t["lng"]})
    options = commute.get("options", [])
    best = commute.get("best")

    for i, o in enumerate(options[:4]):
        icon = "[Bus]" if o["mode"] == "bus" else "[Metro]"
        delay = o.get("totalDelayMinutes", 0) or o.get("delayMinutes", 0)
        conf = o.get("confidence", "?")
        rel = o.get("reliability", 0)
        label = ">> BEST <<" if i == 0 else f"Option {i+1}"
        print(f"\n  {label}")
        print(f"  {icon} {o['routeName']}")
        print(f"  ETA: {o['etaMinutes']} min (range: {o.get('etaRange', ['?','?'])[0]}-{o.get('etaRange', ['?','?'])[1]} min)")
        print(f"  Confidence: {conf.upper()} | Reliability: {(rel*100):.0f}%")
        print(f"  Delay breakdown: {o.get('delayBreakdown', {})}")
        if o.get("trafficNotes"):
            print(f"  Traffic: {', '.join(set(o['trafficNotes']))}")
        print(f"  Score: {o.get('score', '?')} (lower = better)")

    if best:
        print(f"\n  {chr(9654)} RECOMMENDATION: {best['routeName']}")
        print(f"  {chr(9654)} ETA: {best['etaMinutes']} min (range {best.get('etaRange', ['?','?'])[0]}-{best.get('etaRange', ['?','?'])[1]} min)")
        db = best.get("delayBreakdown", {})
        causes = []
        if db.get("trafficImpact", 0) > 0.3: causes.append(f"traffic +{db['trafficImpact']}min")
        if db.get("stopDwellMinutes", 0) > 0.3: causes.append(f"stops +{db['stopDwellMinutes']}min")
        if causes:
            print(f"  {chr(9654)} Delay factors: {', '.join(causes)}")
        print(f"  {chr(9654)} Reliability: {(best.get('reliability', 0)*100):.0f}% on-time history")

    print_header("STEP 3: TRAFFIC & HISTORICAL CONTEXT")
    for h in commute.get("hotspots", []):
        print(f"  {chr(9888)} {h['name']} - typical delay: {h['delay_min']}min")

    print(f"\n  Model has logged {vehicles['activeCount']} vehicles x multiple routes of")
    print(f"  real-time observations feeding into historical delay patterns.")

    print_header("WHAT PRIYA SEES")
    if best:
        eta = best['etaMinutes']
        if eta < 3:
            print(f"\n  \"Bus arriving in {eta} min! She should leave NOW.\"")
        elif eta < 10:
            print(f"\n  \"Bus arriving in {eta} min. She has a few minutes to reach the stop.\"")
        else:
            print(f"\n  \"Bus arriving in {eta} min. She can plan accordingly.\"")
    print()

if __name__ == "__main__":
    try:
        demo_scenario()
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to API at {API}")
        print("Make sure the server is running: python backend/main.py")
        sys.exit(1)
