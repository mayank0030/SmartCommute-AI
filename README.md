# Smart Commute Assistant — Bengaluru

A real-time commute assistant that combines **GTFS transit data** with **simulated live GPS movement** and **ETA prediction logic** to help commuters make smarter travel decisions.

## Problem

Priya's bus is scheduled at 8:22 AM. But it arrives at 8:18, 8:35, or not at all — and she never knows. She leaves too early, waits unnecessarily, or reaches late. This is every commuter, every day.

## Solution

One system that answers: *"When will my bus actually arrive? Is there a better option?"*

## Architecture

```
GTFS Data (BMTC Bengaluru)
    ↓
Route & Stop Graph
    ↓
Simulation Engine → Live GPS positions every 2s
    ↓
Prediction Engine → ETA + Delay + Traffic Detection
    ↓
Route Optimizer → Best option + Multi-modal suggestions
    ↓
┌────────────────┬───────────────┬──────────────┐
│ PWA Web App    │ WhatsApp Bot  │ Lightweight  │
│ (Leaflet map,  │ (Twilio,      │ Web App      │
│ real-time)     │ zero-install) │ (<50KB)      │
└────────────────┴───────────────┴──────────────┘
```

## Quick Start

```bash
pip install -r backend/requirements.txt
cd backend
python main.py
```

Open http://localhost:8000/app in your browser.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Server info |
| `GET /vehicles` | All active vehicle positions |
| `GET /vehicles/near?lat=&lng=` | Vehicles near location |
| `GET /commute?from_lat=&from_lng=&to_lat=&to_lng=` | Full commute analysis |
| `GET /routes` | List all GTFS routes |
| `GET /route/{id}` | Route details + shape + stops |
| `GET /stops` | Search stops |
| `GET /traffic` | Known traffic hotspots |
| `GET /demo` | Demo scenario config |
| `POST /whatsapp/webhook` | Twilio WhatsApp webhook |
| `GET /app/` | Frontend web app |

## Demo Scenario

```bash
python demo/scenario.py
```

Output:
```
  >> BEST <<
  [Bus] 171-G
  ETA: 2.6 min | On time

  Option 2
  [Bus] KBS-3A (via Silk Board)
  ETA: 8.4 min | On time

  Option 3
  [Metro] Metro Purple Line
  ETA: 12.0 min | On time

  ▶ RECOMMENDATION: Take 171-G
  ▶ Bus arriving in 2.6 min! She should leave NOW.
```

## Tech Stack

- **Backend**: Python 3.14, FastAPI, uvicorn
- **Data**: Real BMTC GTFS (4164 routes, 9596 stops, 55071 trips)
- **Simulation**: Custom engine — vehicles follow real GTFS shapes
- **Prediction**: Distance/speed ETA + traffic-weighted delay
- **Frontend**: Vanilla JS, Leaflet.js, CSS (no frameworks, <50KB)
- **PWA**: Service Worker + manifest.json (installable, offline-capable)
- **WhatsApp**: Twilio TwiML webhook

## Scoring Criteria

| Criterion | How We Address It |
|-----------|------------------|
| **Usefulness** | Real GTFS data + live simulation = believable, actionable ETAs |
| **Accuracy** | Traffic-weighted prediction with hotspot-aware delay |
| **Simplicity** | One query: "Home to Office" → route cards with clear recommendations |
| **Performance** | <50KB frontend, works on 2G/basic phones, PWA installable |
