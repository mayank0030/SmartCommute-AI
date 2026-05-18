import os, json, logging
import requests
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/whatsapp")

USER_SESSIONS = {}

COORDS = {
    "koramangala": (12.9352, 77.6245), "home": (12.9352, 77.6245),
    "mg road": (12.9756, 77.6066), "office": (12.9756, 77.6066),
    "majestic": (12.9767, 77.5713), "silboard": (12.9178, 77.6227),
    "electronic city": (12.8456, 77.6603),
}


def query_api(from_lat, from_lng, to_lat=12.9756, to_lng=77.6066):
    base = os.environ.get("API_URL", "http://127.0.0.1:8000")
    url = f"{base}/commute?from_lat={from_lat}&from_lng={from_lng}&to_lat={to_lat}&to_lng={to_lng}"
    resp = requests.get(url, timeout=10)
    return resp.json()


def format_response(data):
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


@router.post("/webhook")
async def webhook(request: Request, Body: str = Form(""), From: str = Form("")):
    resp = MessagingResponse()
    msg = Body.strip().lower()
    sender = From

    if not msg:
        resp.message("Welcome! Send your route like: 'Home to Office'")
        return Response(str(resp), media_type="application/xml")

    parts = msg.replace(" to ", "|").replace(" → ", "|").split("|")
    from_loc = parts[0].strip()
    to_loc = parts[1].strip() if len(parts) >= 2 else "office"

    if parts[0].isdigit() and sender in USER_SESSIONS:
        idx = int(parts[0]) - 1
        session = USER_SESSIONS[sender]
        if "options" in session and 0 <= idx < len(session["options"]):
            opt = session["options"][idx]
            detail = (f"*{opt['routeName']}*\nETA: {opt['etaMinutes']}min\n"
                      f"Delay: {opt['delayMinutes']}min\nMode: {opt['mode'].upper()}\n"
                      f"Occupancy: {opt.get('occupancy', 'N/A')}")
            if opt.get("trafficNotes"):
                detail += f"\nTraffic: {', '.join(opt['trafficNotes'])}"
            resp.message(detail)
            return Response(str(resp), media_type="application/xml")

    from_coords = None
    for key, coords in COORDS.items():
        if key in from_loc:
            from_coords = coords
            break
    if not from_coords:
        resp.message("Send a route like: 'Home to Office'")
        return Response(str(resp), media_type="application/xml")

    try:
        data = query_api(from_coords[0], from_coords[1])
        reply = format_response(data)
        USER_SESSIONS[sender] = data
        resp.message(reply)
    except Exception as e:
        logging.error(f"API error: {e}")
        resp.message("Sorry, couldn't get live data. Try again.")

    return Response(str(resp), media_type="application/xml")
