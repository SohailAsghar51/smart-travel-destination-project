"""
Map pictures for the app (not live maps — we only build *image URLs*).

We use Google "Static Map" (one image file). You need GOOGLE_MAPS_API_KEY in .env
and the Static Maps API turned on in Google Cloud. If the key is missing, functions
return None and the app uses a photo (Unsplash) or something else.
"""

from urllib.parse import urlencode

from config import GOOGLE_MAPS_API_KEY

# Google endpoint for a single PNG/JPEG map image
STATIC_BASE = "https://maps.googleapis.com/maps/api/staticmap"


def destination_hero_image_url(latitude, longitude, size="1200x500", zoom=11):
    """
    One static map: center on the place, one pin. Used for destination cards and headers.

    `latitude` / `longitude` must be numbers. Returns None if there is no API key
    or the coordinates are bad.
    """
    if not GOOGLE_MAPS_API_KEY or latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    parts = (size or "1200x500").lower().split("x")
    w, h = parts[0] if len(parts) > 0 else "1200", parts[1] if len(parts) > 1 else "500"
    params = {
        "center": f"{lat:.6f},{lon:.6f}",
        "zoom": str(int(zoom)),
        "size": f"{w}x{h}",
        "maptype": "terrain",
        "markers": f"color:0x1d4ed8|{lat:.6f},{lon:.6f}",
        "scale": "2",
        "key": GOOGLE_MAPS_API_KEY,
    }
    return f"{STATIC_BASE}?{urlencode(params)}"


def itinerary_map_image_url(locations, size="1000x480", max_markers=15):
    """
    One static map with many pins (for a saved or AI day-by-day plan).

    `locations` = list of dicts with latitude/longitude (or lat/lon) or (lat, lon) pairs.
    We skip bad points. If there is only one point, we reuse the single-place helper above.
    """
    if not GOOGLE_MAPS_API_KEY or not locations:
        return None
    pts = []
    for p in locations[: int(max_markers)]:
        if isinstance(p, dict):
            try:
                la = float(p.get("latitude") or p.get("lat"))
                lo = float(p.get("longitude") or p.get("lon"))
            except (TypeError, ValueError, AttributeError):
                continue
        else:
            try:
                la, lo = float(p[0]), float(p[1])
            except (TypeError, ValueError, IndexError):
                continue
        pts.append((la, lo))
    if not pts:
        return None
    sparts = (size or "1000x480").lower().split("x")
    sw, sh = sparts[0] if sparts else "1000", sparts[1] if len(sparts) > 1 else "480"
    if len(pts) == 1:
        return destination_hero_image_url(pts[0][0], pts[0][1], size=f"{sw}x{sh}", zoom=12)
    # Many points: fit the box that contains all markers (with a small border)
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    pad = 0.02
    min_lat, max_lat = min(lats) - pad, max(lats) + pad
    min_lon, max_lon = min(lons) - pad, max(lons) + pad
    q = [
        ("size", f"{sw}x{sh}"),
        ("maptype", "roadmap"),
        ("visible", f"{min_lat},{min_lon}|{max_lat},{max_lon}"),
        ("scale", "2"),
        ("key", GOOGLE_MAPS_API_KEY),
    ]
    for i, (la, lo) in enumerate(pts):
        color = "0x1d4ed8" if i == 0 else "0xdc2626"
        q.append(("markers", f"color:{color}|size:mid|{la:.5f},{lo:.5f}"))
    return f"{STATIC_BASE}?{urlencode(q, doseq=True)}"


def collect_itinerary_map_points(itinerary, destination_row=None):
    """
    Build a clean list of map points: destination first, then each day’s items (no duplicates).

    `itinerary` = the JSON structure with days and items. `destination_row` = the main
    destination from the database (so the map always starts there if we have coordinates).
    """
    out = []
    seen = set()

    def add_pt(la, lo):
        if la is None or lo is None:
            return
        try:
            a, b = float(la), float(lo)
        except (TypeError, ValueError):
            return
        key = (round(a, 5), round(b, 5))
        if key in seen:
            return
        seen.add(key)
        out.append({"latitude": a, "longitude": b})

    if destination_row and isinstance(destination_row, dict):
        add_pt(destination_row.get("latitude"), destination_row.get("longitude"))
    for day in itinerary or []:
        for it in day.get("items") or []:
            add_pt(it.get("latitude"), it.get("longitude"))
    return out
