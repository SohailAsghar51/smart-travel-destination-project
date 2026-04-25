"""
Map preview images: single image URLs (no JavaScript) using OpenStreetMap data.

We use the public static map service at staticmap.openstreetmap.de — no API key.
For heavy production traffic, host your own static map service or use tiles + a map library
on the client instead.
"""

from urllib.parse import urlencode

# Public OSM static map (Mapnik). No key; be respectful of load (cache if you scale up).
_OSM_STATIC = "https://staticmap.openstreetmap.de/staticmap.php"


def _parse_wh(size: str) -> tuple[int, int]:
    parts = (size or "800x400").lower().split("x")
    try:
        w = int(parts[0]) if len(parts) > 0 else 800
    except ValueError:
        w = 800
    try:
        h = int(parts[1]) if len(parts) > 1 else 400
    except ValueError:
        h = 400
    # Service limits vary; keep reasonable.
    w = max(50, min(w, 1280))
    h = max(50, min(h, 1280))
    return w, h


def _zoom_for_spread(dlat: float, dlon: float) -> int:
    """
    Pick zoom level from geographic span in degrees. Higher = closer in (max ~17 for static service).
    Bias a bit tight so single-city / local pins are not comically wide.
    """
    span = max(dlat, dlon, 0.0001)
    if span > 8.0:
        return 7
    if span > 3.0:
        return 8
    if span > 1.0:
        return 9
    if span > 0.4:
        return 10
    if span > 0.15:
        return 11
    if span > 0.06:
        return 12
    if span > 0.025:
        return 13
    if span > 0.012:
        return 14
    if span > 0.006:
        return 15
    return 16


def destination_hero_image_url(latitude, longitude, size="1200x500", zoom=13):
    """
    One static map: center on a single coordinate with one pin.

    Returns None only if coordinates are missing or not numeric.
    """
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    w, h = _parse_wh(size)
    z = max(1, min(18, int(zoom)))
    q = [
        ("center", f"{lat:.6f},{lon:.6f}"),
        ("zoom", str(z)),
        ("size", f"{w}x{h}"),
        ("maptype", "mapnik"),
        ("markers", f"{lat:.6f},{lon:.6f},red-pushpin"),
    ]
    return f"{_OSM_STATIC}?{urlencode(q)}"


def itinerary_map_image_url(locations, size="1000x480", max_markers=15):
    """
    One static map with several pins. Points need latitude/longitude (or lat/lon).

    We skip bad points. Single-point case uses a slightly closer zoom.
    """
    if not locations:
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
    w, h = _parse_wh(size)
    if len(pts) == 1:
        return destination_hero_image_url(pts[0][0], pts[0][1], size=f"{w}x{h}", zoom=15)
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    dlat = max(lats) - min(lats)
    dlon = max(lons) - min(lons)
    clat = (min(lats) + max(lats)) / 2.0
    clon = (min(lons) + max(lons)) / 2.0
    z = min(17, _zoom_for_spread(dlat, dlon) + 1)  # nudge one level closer; cap for static service
    q: list = [
        ("center", f"{clat:.6f},{clon:.6f}"),
        ("zoom", str(z)),
        ("size", f"{w}x{h}"),
        ("maptype", "mapnik"),
    ]
    for i, (la, lo) in enumerate(pts):
        icon = "red-pushpin" if i == 0 else "ltinyred"
        q.append(("markers", f"{la:.5f},{lo:.5f},{icon}"))
    return f"{_OSM_STATIC}?{urlencode(q, doseq=True)}"


def collect_itinerary_map_points(itinerary, destination_row=None):
    """
    Build a clean list of map points: destination first, then each day's items (no duplicates).

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


def collect_trip_map_points(itinerary, destination_row, places_list=None, max_markers=15):
    """
    Map pins for a trip: same as collect_itinerary_map_points, then add DB place coordinates
    so the static map still shows real POIs when the plan has no per-item lat/lon (e.g. rule-based fallback).
    """
    out = collect_itinerary_map_points(itinerary, destination_row)
    if not places_list:
        return out[: int(max_markers)]
    seen = {(round(p["latitude"], 5), round(p["longitude"], 5)) for p in out}
    for pl in places_list:
        if len(out) >= int(max_markers):
            break
        la, lo = pl.get("latitude"), pl.get("longitude")
        if la is None or lo is None:
            continue
        try:
            a, b = float(la), float(lo)
        except (TypeError, ValueError):
            continue
        key = (round(a, 5), round(b, 5))
        if key in seen:
            continue
        seen.add(key)
        out.append({"latitude": a, "longitude": b})
    return out[: int(max_markers)]
