import asyncio
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi import Form
from twilio.twiml.messaging_response import MessagingResponse
from gtfs_loader import GTFSLoader
from simulation import SimulationEngine

from routing import build_commute_options, get_best_option
from traffic import HOTSPOTS
from departure import departure_what_if

import os
app = FastAPI(title="Commute Assistant API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

gtfs = GTFSLoader().load()
sim = SimulationEngine(gtfs)

DEMO_ROUTE_IDS = ["995", "1066", "2261", "1789", "1008", "1007", "6575", "1013"]

print(f"Seeding {len(DEMO_ROUTE_IDS)} demo routes: {DEMO_ROUTE_IDS}")
sim.seed_vehicles(route_ids=DEMO_ROUTE_IDS if DEMO_ROUTE_IDS else None, count_per_route=6)
sim.historical_model.load()


async def simulation_loop():
    save_counter = 0
    while True:
        sim.update_all(dt_seconds=2)
        save_counter += 1
        if save_counter % 50 == 0:
            sim.historical_model.save()
        await asyncio.sleep(0.1)


@app.on_event("startup")
async def startup():
    asyncio.create_task(simulation_loop())


@app.get("/")
def root():
    return {"app": "Smart Commute Assistant", "city": "Bengaluru", "version": "1.0.0"}


@app.get("/routes")
def list_routes(query: str = "", limit: int = 50):
    results = []
    for r in gtfs.routes.values():
        name = f'{r.get("short_name", "")} {r.get("long_name", "")}'.lower()
        if query and query.lower() not in name:
            continue
        results.append({"id": r["id"], "shortName": r.get("short_name", ""), "longName": r.get("long_name", ""), "type": r["type"]})
    return {"routes": results[:limit], "total": len(results)}


@app.get("/vehicles")
def get_vehicles():
    return sim.get_state()


@app.get("/vehicles/near")
def vehicles_near(lat: float = Query(...), lng: float = Query(...), radius: float = 2.0):
    return {"vehicles": sim.get_vehicles_near(lat, lng, radius)}


@app.get("/eta")
def get_eta(stop_lat: float = Query(...), stop_lng: float = Query(...)):
    etas = sim.get_eta_to_stop(stop_lat, stop_lng)
    return {"etas": etas}


@app.get("/commute")
def commute(
    from_lat: float = Query(...), from_lng: float = Query(...),
    to_lat: float = Query(...), to_lng: float = Query(...),
):
    options = build_commute_options(gtfs, sim, from_lat, from_lng, to_lat, to_lng)
    best = get_best_option(options)
    return {"options": options, "best": best, "hotspots": HOTSPOTS}


@app.get("/traffic")
def traffic_hotspots():
    return {"hotspots": HOTSPOTS}


@app.get("/stops")
def list_stops(query: str = "", limit: int = 20):
    results = []
    for s in gtfs.stops.values():
        if query and query.lower() not in s["name"].lower():
            continue
        results.append({"id": s["id"], "name": s["name"], "lat": s["lat"], "lng": s["lng"]})
    return {"stops": results[:limit]}


@app.get("/route/{route_id}")
def route_detail(route_id: str):
    route = gtfs.routes.get(route_id)
    if not route:
        return JSONResponse({"error": "Route not found"}, 404)
    stops = gtfs.get_route_stops(route_id)
    shape = gtfs.get_route_shape(route_id)
    active_vehicles = [v.to_dict() for v in sim.vehicles.values() if v.route_id == route_id and v.active]
    return {
        "route": route,
        "stops": stops,
        "shape": shape,
        "vehicleCount": len(active_vehicles),
        "vehicles": active_vehicles,
    }


@app.get("/demo")
def demo_scenario():
    """Returns a pre-configured demo scenario: Home to Office in Bengaluru."""
    return {
        "title": "Priya's Morning Commute",
        "from": {"name": "Koramangala (Home)", "lat": 12.9352, "lng": 77.6245},
        "to": {"name": "MG Road (Office)", "lat": 12.9756, "lng": 77.6066},
        "description": "Priya needs to reach office by 9 AM. Bus 14A usually comes at 8:22.",
    }


@app.get("/departure-plan")
def get_departure_plan(from_lat: float = Query(...), from_lng: float = Query(...),
                       to_lat: float = Query(...), to_lng: float = Query(...)):
    return departure_what_if(gtfs, sim, from_lat, from_lng, to_lat, to_lng)


@app.get("/departure-plan/demo")
def departure_plan_demo():
    d = departure_what_if(gtfs, sim, 12.9352, 77.6245, 12.9756, 77.6066)
    return d


WHATSAPP_COORDS = {
    "koramangala": (12.9352, 77.6245), "home": (12.9352, 77.6245),
    "mg road": (12.9756, 77.6066), "office": (12.9756, 77.6066),
    "majestic": (12.9767, 77.5713), "silboard": (12.9178, 77.6227),
    "electronic city": (12.8456, 77.6603),
}
WA_SESSIONS = {}


def _wa_format(data):
    options = data.get("options", [])
    best = data.get("best")
    if not options:
        return "No routes available near your location."
    lines = ["📍 *Smart Commute Update*", ""]
    for i, o in enumerate(options[:3]):
        icon = "🚌" if o["mode"] == "bus" else "🚇"
        delay = f"⚠️ +{o['delayMinutes']}min delay" if o["delayMinutes"] > 1 else "✅ On time"
        traffic = ""
        if o.get("trafficNotes"):
            traffic = f"\n   🚦 {', '.join(o['trafficNotes'][:2])}"
        lines.append(f"{icon} *{o['routeName']}*")
        lines.append(f"   Arriving: {o['etaMinutes']}min | {delay}{traffic}")
        lines.append("")
    if best:
        lines.append(f"💡 *Suggested:* {best['routeName']} ({best['etaMinutes']}min)")
        if best.get("trafficNotes"):
            lines.append(f"⚠️ Traffic: {', '.join(best['trafficNotes'][:2])}")
    lines.append("")
    lines.append("Reply with number for details, or type a route")
    return "\n".join(lines)


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(Body: str = Form(""), From: str = Form("")):
    resp = MessagingResponse()
    msg = Body.strip().lower()
    sender = From
    if not msg:
        resp.message("Welcome! Send your route like: 'Home to Office'")
        return Response(str(resp), media_type="application/xml")
    parts = msg.replace(" to ", "|").replace(" → ", "|").split("|")
    if parts[0].isdigit() and sender in WA_SESSIONS:
        idx = int(parts[0]) - 1
        opts = WA_SESSIONS[sender].get("options", [])
        if 0 <= idx < len(opts):
            o = opts[idx]
            d = (f"*{o['routeName']}*\nETA: {o['etaMinutes']}min\n"
                 f"Delay: {o['delayMinutes']}min\nMode: {o['mode'].upper()}\n"
                 f"Occupancy: {o.get('occupancy', 'N/A')}")
            if o.get("trafficNotes"):
                d += f"\nTraffic: {', '.join(o['trafficNotes'])}"
            resp.message(d)
            return Response(str(resp), media_type="application/xml")
    from_coords = None
    for key, coords in WHATSAPP_COORDS.items():
        if key in parts[0].strip():
            from_coords = coords
            break
    if not from_coords:
        resp.message("Send a route like: 'Home to Office'")
        return Response(str(resp), media_type="application/xml")
    try:
        import requests as req
        url = f"{os.environ.get('API_URL', 'http://127.0.0.1:8000')}/commute?from_lat={from_coords[0]}&from_lng={from_coords[1]}"
        r = req.get(url, timeout=10)
        data = r.json()
        reply = _wa_format(data)
        WA_SESSIONS[sender] = data
        resp.message(reply)
    except Exception as e:
        print(f"WA error: {e}")
        resp.message("Sorry, couldn't get live data. Try again.")
    return Response(str(resp), media_type="application/xml")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
