#!/usr/bin/env python3
"""Publish validated worldwide disaster alerts from GDACS."""
import datetime as dt
import json
import pathlib
import urllib.request

URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
req = urllib.request.Request(URL, headers={"User-Agent": "GlobalSecurityMonitor/1.0", "Accept": "application/json"})
with urllib.request.urlopen(req, timeout=35) as response:
    data = json.load(response)
if not isinstance(data, dict) or not isinstance(data.get("features"), list):
    raise ValueError("Unexpected GDACS GeoJSON format")
events = []
for f in data["features"]:
    if not isinstance(f, dict):
        continue
    p = f.get("properties") or {}
    geometry = f.get("geometry") or {}
    coords = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coords, list) or len(coords) < 2:
        continue
    try:
        lon, lat = float(coords[0]), float(coords[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            continue
    except (TypeError, ValueError):
        continue
    events.append({"id": str(p.get("eventid") or f.get("id") or "")[:100],
                   "type": str(p.get("eventtype") or "")[:30],
                   "title": str(p.get("name") or p.get("description") or "GDACS Ereignis")[:250],
                   "level": str(p.get("alertlevel") or "unknown")[:30],
                   "lat": lat, "lon": lon,
                   "url": str(p.get("url") or "https://www.gdacs.org/")[:500]})
output = {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "source": URL, "events": events[:500]}
pathlib.Path("global-disasters.json").write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"GDACS events: {len(events)}")
