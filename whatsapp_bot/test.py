"""Simulate WhatsApp bot interaction without Twilio."""
import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "http://127.0.0.1:8000"

ICONS = {"bus": "[Bus]", "metro": "[Metro]"}

def simulate(msg):
    print(f"\n{'='*50}")
    print(f"User: {msg}")
    parts = msg.lower().replace(" to ", "|").split("|")
    from_loc = parts[0].strip()

    coords_map = {
        "home": (12.9352, 77.6245), "koramangala": (12.9352, 77.6245),
        "office": (12.9756, 77.6066), "mg road": (12.9756, 77.6066),
    }
    fc = coords_map.get(from_loc)
    if not fc:
        print("Bot: Please send a route like 'Home to Office'")
        return

    r = requests.get(f"{BASE}/commute", params={"from_lat": fc[0], "from_lng": fc[1]})
    data = r.json()
    options = data.get("options", [])
    best = data.get("best")

    print("\nBot:")
    print("*Smart Commute Update*")
    for i, o in enumerate(options[:3]):
        icon = ICONS.get(o["mode"], "[?]")
        delay = f"DELAY +{o['delayMinutes']}min" if o["delayMinutes"] > 1 else "On time"
        print(f"  {icon} {o['routeName']} - {o['etaMinutes']}min | {delay}")
        if o.get("trafficNotes"):
            print(f"     Traffic: {', '.join(o['trafficNotes'][:2])}")

    if best:
        print(f"\n  >> Suggested: {best['routeName']} ({best['etaMinutes']}min)")
        if best.get("trafficNotes"):
            print(f"  >> Traffic: {', '.join(best['trafficNotes'][:2])}")

if __name__ == "__main__":
    simulate("Home to Office")
    simulate("Koramangala to MG Road")
