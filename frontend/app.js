const API = window.location.origin;
const DEMO_FROM = { name: "Koramangala (Home)", lat: 12.9352, lng: 77.6245 };
const DEMO_TO = { name: "MG Road (Office)", lat: 12.9756, lng: 77.6066 };

let map, vehicleLayer, vehicleMarkers = {}, routeLines = {}, updateInterval, currentRouteId = null;

function init() {
  document.getElementById("loading").style.display = "none";
  document.getElementById("app").style.display = "block";

  map = L.map("map", { zoomControl: false, attributionControl: false }).setView([12.955, 77.64], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(map);
  L.marker([DEMO_FROM.lat, DEMO_FROM.lng]).addTo(map).bindPopup("<b>Home</b><br>Koramangala");
  L.marker([DEMO_TO.lat, DEMO_TO.lng]).addTo(map).bindPopup("<b>Office</b><br>MG Road");

  vehicleLayer = L.layerGroup().addTo(map);
  loadCommute();
  updateInterval = setInterval(loadCommute, 3000);

  document.getElementById("routeSearch").addEventListener("input", searchRoutes);
}

function showError(msg) {
  const bar = document.getElementById("errorBar");
  bar.textContent = msg;
  bar.style.display = "block";
  setTimeout(() => { bar.style.display = "none"; }, 5000);
}

async function loadCommute() {
  try {
    const [vehiclesRes, commuteRes, departureRes, searchRes] = await Promise.all([
      fetch(`${API}/vehicles`),
      fetch(`${API}/commute?from_lat=${DEMO_FROM.lat}&from_lng=${DEMO_FROM.lng}&to_lat=${DEMO_TO.lat}&to_lng=${DEMO_TO.lng}`),
      fetch(`${API}/departure-plan?from_lat=${DEMO_FROM.lat}&from_lng=${DEMO_FROM.lng}&to_lat=${DEMO_TO.lat}&to_lng=${DEMO_TO.lng}`),
      currentRouteId ? fetch(`${API}/route/${currentRouteId}`) : Promise.resolve(null)
    ]);
    if (!vehiclesRes.ok || !commuteRes.ok) throw new Error("API error");
    const vehicles = await vehiclesRes.json();
    const commute = await commuteRes.json();
    const departure = await departureRes.json();
    if (searchRes && searchRes.ok) {
      const routeDetail = await searchRes.json();
      if (routeDetail.shape) updateRouteShape(routeDetail);
    }
    updateVehicles(vehicles);
    updateCommute(commute);
    updateDeparture(departure);
    updateStats(vehicles);
    updateTime(vehicles.timeOfDay);
  } catch (e) {
    showError("Connection lost. Retrying...");
  }
}

function updateDeparture(data) {
  const el = document.getElementById("departureContent");
  if (!data || !data.bestNow) { el.innerHTML = ""; return; }
  let html = `<div class="option">
    <div class="option-row">
      <div><span class="route-name">🚀 ${data.bestRoute}</span></div>
      <div style="text-align:right"><span class="eta-value">${data.bestEta}</span><span class="eta-unit"> min</span></div>
    </div>
    <div class="suggestion" style="margin-top:6px">
      <div class="suggestion-text">${data.recommendation}</div>
    </div>`;
  if (data.scenarios && data.scenarios.length > 1) {
    html += `<div style="margin-top:8px;font-size:12px;color:#8b949e">⏱ Departure timeline:</div>
      <div style="display:flex;gap:6px;margin-top:4px;overflow-x:auto">`;
    data.scenarios.forEach((s, i) => {
      const active = s.delayMinutes === 0 ? "background:#1a2e1a;border:1px solid #238636" : "background:#161b22;border:1px solid #30363d";
      const eta = s.eta || data.bestEta;
      html += `<div style="${active};border-radius:6px;padding:8px 12px;min-width:80px;text-align:center;flex-shrink:0">
        <div style="font-size:10px;color:#8b949e">${s.label}</div>
        <div style="font-size:16px;font-weight:700;color:#58a6ff">${eta}<span style="font-size:10px;color:#8b949e">m</span></div>
      </div>`;
    });
    html += `</div>`;
  }
  if (data.peakHour) {
    html += `<div style="margin-top:6px;font-size:11px;color:#d29922">⚠️ Peak hour traffic — expect variations</div>`;
  }
  html += `</div>`;
  el.innerHTML = html;
}

function updateVehicles(data) {
  const active = data.vehicles || [];
  const currentIds = new Set(active.map(v => v.id));
  for (const id in vehicleMarkers) {
    if (!currentIds.has(id)) { map.removeLayer(vehicleMarkers[id]); delete vehicleMarkers[id]; }
  }
  active.forEach(v => {
    const delayColor = v.onTime ? "#3fb950" : v.delayMinutes > 3 ? "#da3633" : "#d29922";
    const icon = L.divIcon({
      html: `<div style="background:${delayColor};width:11px;height:11px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,0.5)"></div>`,
      iconSize: [11, 11], className: ""
    });
    if (vehicleMarkers[v.id]) {
      vehicleMarkers[v.id].setLatLng([v.lat, v.lng]);
    } else {
      const marker = L.marker([v.lat, v.lng], { icon }).addTo(vehicleLayer);
      marker.bindPopup(`<b>${v.routeName}</b><br>Speed: ${v.speed} km/h<br>Delay: ${v.delayMinutes} min<br>Occ: ${v.occupancy}%`);
      vehicleMarkers[v.id] = marker;
    }
  });
}

function updateRouteShape(data) {
  for (const k in routeLines) { map.removeLayer(routeLines[k]); delete routeLines[k]; }
  if (!data.shape || !data.shape.length) return;
  const coords = data.shape.map(p => [p.lat, p.lng]);
  const line = L.polyline(coords, { color: "#58a6ff", weight: 3, opacity: 0.6 }).addTo(map);
  routeLines["shape"] = line;
  if (data.stops) {
    const stopMarkers = L.layerGroup();
    data.stops.forEach(s => {
      L.circleMarker([s.lat, s.lng], { radius: 3, color: "#8b949e", fillColor: "#8b949e", fillOpacity: 0.8 })
        .addTo(stopMarkers).bindPopup(s.name);
    });
    stopMarkers.addTo(map);
    routeLines["stops"] = stopMarkers;
  }
}

function updateCommute(data) {
  const options = data.options || [];
  const best = data.best;
  document.getElementById("bestContent").innerHTML = best ? renderOption(best, true) : "";
  document.getElementById("optionsContent").innerHTML = options.length
    ? options.map((o, i) => renderOption(o, false, i === 0, i)).join("")
    : '<div style="padding:14px;color:#8b949e;text-align:center">No routes nearby</div>';
}

function renderOption(o, isBest, highlight, idx) {
  const icon = o.mode === "metro" ? "🚇" : "🚌";
  const delay = o.totalDelayMinutes || o.delayMinutes || 0;
  const delayHtml = delay > 1
    ? `<span class="delay-badge">+${delay.toFixed(1)}min delay</span>`
    : `<span class="delay-none">On time</span>`;
  const confColor = o.confidence === "high" ? "#3fb950" : o.confidence === "medium" ? "#d29922" : "#da3633";
  const bg = highlight ? "background:#1a2e1a;border-radius:8px;padding:12px;margin-bottom:8px;border:1px solid #238636" : "";

  let breakdownHtml = "";
  if (o.delayBreakdown) {
    const b = o.delayBreakdown;
    const parts = [];
    if (b.trafficImpact > 0.3) parts.push(`Traffic +${b.trafficImpact.toFixed(1)}m`);
    if (b.stopDwellMinutes > 0.3) parts.push(`Stops +${b.stopDwellMinutes.toFixed(1)}m`);
    if (b.historicalAdjustment > 0.3) parts.push(`History +${b.historicalAdjustment.toFixed(1)}m`);
    if (parts.length) breakdownHtml = `<div style="font-size:11px;color:#8b949e;margin-top:2px">${parts.join(" | ")}</div>`;
  }

  const walkHtml = o.walkMinutes
    ? `<span style="font-size:11px;color:#8b949e;margin-left:8px">🚶 ${o.walkMinutes}min walk</span>`
    : "";
  const rangeHtml = o.etaRange
    ? `<div style="font-size:11px;color:#8b949e">Range: ${o.etaRange[0]}-${o.etaRange[1]} min</div>`
    : "";
  const relHtml = o.reliability
    ? `<span style="font-size:11px;color:#8b949e;margin-left:6px">${(o.reliability*100).toFixed(0)}% reliable</span>`
    : "";

  return `
    <div class="option" style="${bg}" onclick="showRoute('${o.routeId}')">
      <div class="option-row">
        <div>
          <span class="route-name">${icon} ${o.routeName}</span>
          <span class="route-mode">${o.mode.toUpperCase()}</span>
          <span style="display:inline-block;background:${confColor};color:#fff;font-size:10px;padding:1px 6px;border-radius:3px;margin-left:4px">${o.confidence}</span>
          ${relHtml}
        </div>
        <div style="text-align:right">
          <span class="eta-value">${o.etaMinutes}</span>
          <span class="eta-unit">min</span>
          ${delayHtml}
        </div>
      </div>
      ${walkHtml}
      ${rangeHtml}
      ${breakdownHtml}
      ${o.trafficNotes && o.trafficNotes.length ? `<div class="traffic-note">⚠️ ${[...new Set(o.trafficNotes)].join(", ")}</div>` : ""}
      ${isBest ? bestSuggestion(o) : ""}
      <div style="font-size:10px;color:#484f58;margin-top:4px">Click to view route on map</div>
    </div>`;
}

function bestSuggestion(o) {
  if (o.mode === "metro") return `<div class="suggestion"><div class="suggestion-text">💡 Take Metro — avoids traffic, reliable ETA</div></div>`;
  if (o.walkMinutes && o.walkMinutes > 5) return `<div class="suggestion"><div class="suggestion-text">🚶 ${o.walkMinutes}min walk to stop — plan accordingly</div></div>`;
  if (o.totalDelayMinutes > 3) return `<div class="suggestion"><div class="suggestion-text">⚠️ ${o.totalDelayMinutes.toFixed(1)}min delay — consider alternatives</div></div>`;
  return `<div class="suggestion"><div class="suggestion-text">✅ Best option — lowest total travel time</div></div>`;
}

async function showRoute(routeId) {
  currentRouteId = routeId;
  try {
    const r = await fetch(`${API}/route/${routeId}`);
    if (!r.ok) return;
    const data = await r.json();
    if (data.shape) updateRouteShape(data);
  } catch (e) {}
}

async function searchRoutes() {
  const q = document.getElementById("routeSearch").value.trim();
  const results = document.getElementById("searchResults");
  if (q.length < 2) { results.innerHTML = ""; results.style.display = "none"; return; }
  try {
    const r = await fetch(`${API}/routes?query=${encodeURIComponent(q)}&limit=8`);
    const data = await r.json();
    if (!data.routes || !data.routes.length) { results.innerHTML = "<div style='padding:8px;color:#8b949e'>No routes found</div>"; results.style.display = "block"; return; }
    results.innerHTML = data.routes.map(rt =>
      `<div class="search-item" onclick="showRoute('${rt.id}')">[${rt.shortName}] ${rt.longName.substring(0, 50)}</div>`
    ).join("");
    results.style.display = "block";
  } catch (e) {}
}
document.addEventListener("click", (e) => {
  if (!e.target.closest("#searchBox")) document.getElementById("searchResults").style.display = "none";
});

function updateStats(data) {
  const vehicles = data.vehicles || [];
  const delayed = vehicles.filter(v => !v.onTime);
  document.getElementById("statsContent").innerHTML = `
    <div class="stats-grid">
      <div class="stat-item"><div class="stat-value">${data.activeCount || 0}</div><div class="stat-label">Active</div></div>
      <div class="stat-item"><div class="stat-value">${vehicles.length - delayed.length}</div><div class="stat-label">On Time</div></div>
      <div class="stat-item"><div class="stat-value">${delayed.length}</div><div class="stat-label">Delayed</div></div>
    </div>
    <div style="padding:0 14px 10px;font-size:11px;color:#8b949e">
      ${delayed.length ? `⚠️ ${delayed.slice(0,2).map(v => v.routeName).join(", ")} delayed` : "✅ All buses on time"}
    </div>`;
}

function updateTime(tod) {
  const h = Math.floor(tod);
  const m = Math.floor((tod - h) * 60);
  document.getElementById("timeDisplay").textContent =
    `🕐 ${h.toString().padStart(2,"0")}:${m.toString().padStart(2,"0")}`;
}

document.addEventListener("DOMContentLoaded", init);
