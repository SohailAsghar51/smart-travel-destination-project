"""
Smart Travel — Flask HTTP API (this file).

- We define each URL (for example /api/home/) and what it returns (JSON).
- Big jobs are in other folders: db/ (database), clients/ (AI + weather), etc.
- Run:  python api.py   (from the smart_travel_backend folder)
"""

import os
import sys
from pathlib import Path

# So `import db` / `clients` resolve when the app is not launched with cwd = this folder
# (e.g. IDE "Run" from repo root, or `python path/to/api.py`).
_BACKEND_ROOT = Path(__file__).resolve().parent
_root = str(_BACKEND_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash

import db.repository as db
from config import GROQ_API_KEY, GROQ_MODEL, RAPIDAPI_KEY
from clients.weather import fetch_weather_latlon, format_weather_context_for_groq
from clients.groq import (
    build_itinerary_from_places_with_groq,
    build_itinerary_with_groq,
    parse_travel_nlp,
    sum_itinerary_cost_pkr,
)
from maps.static_maps import (
    collect_trip_map_points,
    destination_hero_image_url,
    itinerary_map_image_url,
)
from recommendations import run_recommendation
from search.helpers import select_destinations_for_search

app = Flask(__name__)
# CORS: flask-cors 4 may respond 403 for requests whose Origin is not allowlisted (browser then shows
# "blocked by CORS" with no header). Use * by default in dev; set CORS_ORIGINS to a comma list for production.
# If you see 403 to port 5000 on macOS, try PORT=5001 (AirPlay sometimes binds :5000).
_cors = (os.environ.get("CORS_ORIGINS") or "*").strip()
_cors_headers = ["Content-Type", "Authorization", "X-Requested-With"]
_cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
if _cors == "*":
    CORS(app, origins="*", allow_headers=_cors_headers, methods=_cors_methods)
else:
    CORS(
        app,
        origins=[o.strip() for o in _cors.split(",") if o.strip()],
        allow_headers=_cors_headers,
        methods=_cors_methods,
    )

# Allow URL with or without "/" at the end (both /api/home and /api/home/ work the same)
app.url_map.strict_slashes = False

# Thumbnails: prefer DB `image_url` in enrich_card; else OSM static map / defaults / per-name Unsplash
DEFAULT_DEST_IMAGE = (
    "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60"
)
DESTINATION_IMAGES = {
}


def enrich_card(dest):
    if not dest:
        return None
    d = dict(dest)
    n = (d.get("name") or "").lower()
    url_from_db = (d.get("image_url") or "").strip()
    if url_from_db:
        d["image"] = url_from_db
    else:
        gimg = destination_hero_image_url(d.get("latitude"), d.get("longitude"))
        if gimg:
            d["image"] = gimg
        else:
            d["image"] = DEFAULT_DEST_IMAGE
            for key, url in DESTINATION_IMAGES.items():
                if key in n:
                    d["image"] = url
                    break
    cat = d.get("category") or ""
    d["tags"] = [c.strip().lower() for c in cat.split(",") if c.strip()] or [
        (cat or "travel").lower()
    ]
    d["summary"] = (d.get("description") or "")[:500]
    d["weather"] = d.get("climate") or "—"
    d["best_season"] = d.get("best_season") or "—"
    if "name" in d and d["name"] and d.get("region"):
        d["type"] = d.get("category", "Destination")
    return d


def _attach_trip_destination_image(trip, keep_dest_coordinates=False):
    """
    Fills `image` (and normalized `image_url`) from DB + same fallbacks as enrich_card.
    Expects `dest_latitude` / `dest_longitude` from the trips+destinations join; removes them
    unless keep_dest_coordinates, in which case they become `latitude` / `longitude`.
    """
    if not trip:
        return
    lat = trip.pop("dest_latitude", None)
    lon = trip.pop("dest_longitude", None)
    e = enrich_card(
        {
            "id": str(trip.get("destination_id") or "0"),
            "name": trip.get("destination_name") or "",
            "region": trip.get("region") or "",
            "image_url": trip.get("image_url"),
            "latitude": lat,
            "longitude": lon,
            "category": "",
            "description": "",
        }
    )
    if e:
        trip["image"] = e.get("image")
        trip["image_url"] = e.get("image_url")
    if keep_dest_coordinates:
        trip["latitude"] = lat
        trip["longitude"] = lon


def _parse_profile_body(data):
    # Accept simple form: styles array (DB category slugs, lowercase) + budget (PKR) from the React app
    if not data:
        return {}
    styles = data.get("styles")
    if isinstance(styles, list) and len(styles) > 0:
        norm = [str(s).strip().lower() for s in styles if s and str(s).strip()]
        travel_style = norm[0] if norm else (data.get("preferred_travel_style") or "nature")
        combined = ", ".join(dict.fromkeys(norm))  # de-dupe, preserve order
    else:
        travel_style = (data.get("preferred_travel_style") or "nature")
        if isinstance(travel_style, str):
            travel_style = travel_style.strip().lower()
        combined = data.get("preferred_categories")
        if isinstance(combined, str):
            combined = ", ".join(
                dict.fromkeys(
                    c.strip().lower() for c in combined.split(",") if c and c.strip()
                )
            )
    if data.get("budget") is not None and not data.get("budget_range"):
        b = int(data["budget"])
        if b <= 20000:
            br = "economy"
        elif b <= 50000:
            br = "standard"
        else:
            br = "premium"
    else:
        br = data.get("budget_range")
    if isinstance(styles, list) and data.get("styles") is not None and len(styles) == 0:
        combined = ""
    elif not combined:
        combined = "nature"
    return {
        "preferred_travel_style": travel_style
        or (data.get("preferred_travel_style") or "nature")
        or "nature",
        "budget_range": br or "standard",
        "preferred_categories": combined,
        "typical_trip_duration_days": data.get("typical_trip_duration_days")
        or data.get("duration")
        or 3,
        "preferred_regions": data.get("preferred_regions") or "Pakistan",
    }


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "ok": True,
            "groq_configured": bool(GROQ_API_KEY),
            "groq_model": GROQ_MODEL,
            "static_map_provider": "openstreetmap (no key)",
            "rapidapi_weather_configured": bool(RAPIDAPI_KEY),
        }
    )


@app.route("/api/register", methods=["POST"])
@app.route("/user/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = data.get("name") or data.get("full_name")
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not name or not email or not password:
        return jsonify({"message": "name, email and password are required"}), 400
    user_id = db.create_user_email(name, email, password)
    if not user_id:
        return jsonify({"message": "Email already registered"}), 400
    user = db.get_user_by_id(user_id)
    prof = db.get_profile(user_id) or {}
    return jsonify(
        {
            "message": "User registered",
            "user": {**user, "name": user["full_name"]},
            "profile": _profile_to_frontend(prof),
        }
    )


def _profile_to_frontend(prof):
    if not prof:
        return {
            "budget": 25000,
            "styles": [],
            "duration": 3,
        }
    raw_cats = prof.get("preferred_categories") or prof.get("preferred_travel_style") or ""
    styles = [c.strip().lower() for c in (raw_cats or "").split(",") if c.strip()]
    st = (prof.get("preferred_travel_style") or "").strip().lower()
    if st and st not in styles:
        styles.insert(0, st)
    styles = list(dict.fromkeys(styles))
    bmap = {"economy": 20000, "standard": 40000, "premium": 80000}
    budget = bmap.get((prof.get("budget_range") or "standard").lower(), 20000)
    return {
        "budget": budget,
        "styles": styles,
        "duration": int(prof.get("typical_trip_duration_days") or 3),
    }


@app.route("/api/login", methods=["POST"])
@app.route("/login/", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = data.get("password", "")
    u = db.verify_user_login(email, password)
    if not u:
        return jsonify({"message": "Invalid email or password"}), 401
    user = {**u, "name": u["full_name"]}
    prof = db.get_profile(u["id"]) or {}
    role = (u.get("role") or "user").strip().lower()
    return jsonify(
        {
            "message": "Login successful",
            "data": {
                "name": u["full_name"],
                "email": u["email"],
                "id": u["id"],
                "role": role,
            },
            "user": {**user, "role": role},
            "profile": _profile_to_frontend(prof),
        }
    )


@app.route("/api/profile/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    u = db.get_user_by_id(user_id)
    if not u:
        return jsonify({"message": "User not found"}), 404
    p = db.get_profile(user_id) or {}
    return jsonify(
        {
            "user": {**u, "name": u["full_name"]},
            "profile": _profile_to_frontend(p),
        }
    )


@app.route("/api/profile/<int:user_id>", methods=["PUT", "POST"])
def update_profile(user_id):
    u = db.get_user_by_id(user_id)
    if not u:
        return jsonify({"message": "User not found"}), 404
    body = _parse_profile_body(request.get_json() or {})
    p = body.get("preferred_travel_style")
    b = body.get("budget_range")
    pr = body.get("preferred_regions")
    pc = body.get("preferred_categories")
    td = body.get("typical_trip_duration_days")
    db.update_profile(
        user_id,
        preferred_travel_style=p,
        budget_range=b,
        preferred_regions=pr,
        preferred_categories=pc,
        typical_trip_duration_days=td,
    )
    prof = db.get_profile(user_id) or {}
    return jsonify({"profile": _profile_to_frontend(prof)})


@app.route("/api/destinations", methods=["GET"])
def list_dests():
    limit = int(request.args.get("limit", 100))
    region = request.args.get("region")
    max_p = request.args.get("max_budget_pkr")
    max_p = int(max_p) if max_p else None
    raw = db.list_destinations(limit=limit, region=region, max_budget_pkr=max_p)
    return jsonify([enrich_card(d) for d in raw])


@app.route("/api/destination-categories", methods=["GET"])
def destination_categories():
    """Distinct `destinations.category` values for filter UI (matches database)."""
    return jsonify({"categories": db.list_destination_categories()})


@app.route("/api/destinations/<dest_id>", methods=["GET"])
def one_dest(dest_id):
    d = db.get_destination_by_id(dest_id)
    if not d:
        return jsonify({"message": "Not found"}), 404
    return jsonify(enrich_card(d))


@app.route("/api/destinations/<dest_id>/map-image", methods=["GET"])
def destination_map_image(dest_id):
    """
    Static map image (OpenStreetMap via staticmap.openstreetmap.de) for the destination + catalog places, no AI plan required.
    Used when the trip page cannot build a day-by-day plan but we still want pins.
    """
    try:
        did = int(dest_id)
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid destination id"}), 400
    d = db.get_destination_by_id(did)
    if not d:
        return jsonify({"message": "Not found"}), 404
    dbid = d.get("db_id") or did
    places = db.get_places_by_destination(dbid, limit=120) or []
    pts = collect_trip_map_points([], d, places)
    url = itinerary_map_image_url(pts, size="1200x520")
    if not url and d.get("latitude") is not None and d.get("longitude") is not None:
        url = destination_hero_image_url(d.get("latitude"), d.get("longitude"), size="1200x520")
    return jsonify({"map_image_url": url})


@app.route("/api/destinations/<dest_id>/places", methods=["GET"])
def destination_places(dest_id):
    """POIs (hotels, restaurants, attractions) for one destination (read-only catalog)."""
    try:
        did = int(dest_id)
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid destination id"}), 400
    if not db.get_destination_by_id(did):
        return jsonify({"message": "Not found"}), 404
    places = db.get_places_by_destination(did, limit=300) or []
    return jsonify({"places": places})


def _admin_user_id_from_json():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    try:
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


def _admin_forbidden():
    """Returns a 403 response if the JSON body does not name an admin user, else None."""
    uid = _admin_user_id_from_json()
    if not uid or not db.is_user_admin(uid):
        return jsonify({"message": "Forbidden"}), 403
    return None


@app.route("/api/admin/destinations", methods=["POST"])
def admin_create_destination():
    denied = _admin_forbidden()
    if denied:
        return denied
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    region = (data.get("region") or "").strip()
    category = (data.get("category") or "").strip()
    if not name or not region or not category:
        return jsonify({"message": "name, region, and category are required"}), 400
    try:
        avg_cost = int(data.get("avg_cost_pkr", 0))
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"message": "avg_cost_pkr, latitude, and longitude must be valid numbers"}), 400
    new_id = db.create_destination(
        name,
        region,
        category,
        avg_cost,
        lat,
        lon,
        country=(data.get("country") or "Pakistan").strip(),
        description=(data.get("description") or "").strip() or None,
        best_season=(data.get("best_season") or "").strip() or None,
        climate=(data.get("climate") or "").strip() or None,
        safety_rating=float(data.get("safety_rating", 4.0)),
        rating=float(data.get("rating", 4.0)),
        popularity_score=float(data.get("popularity_score", 0.0)),
        image_url=(data.get("image_url") or "").strip() or None,
    )
    if not new_id:
        return jsonify({"message": "Could not create destination (duplicate name or invalid data)"}), 400
    d = db.get_destination_by_id(new_id)
    return jsonify({"id": new_id, "destination": d}), 201


@app.route("/api/admin/places", methods=["POST"])
def admin_create_place():
    denied = _admin_forbidden()
    if denied:
        return denied
    data = request.get_json() or {}
    try:
        dest_id = int(data.get("destination_id"))
    except (TypeError, ValueError):
        return jsonify({"message": "destination_id is required"}), 400
    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    main_type = (data.get("main_type") or "").strip().lower()
    if not name or not category or not main_type:
        return jsonify({"message": "name, category, and main_type are required"}), 400
    try:
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"message": "latitude and longitude are required"}), 400
    if not db.get_destination_by_id(dest_id):
        return jsonify({"message": "Destination not found"}), 404
    cost_raw = data.get("cost_pkr")
    try:
        cost = int(cost_raw) if cost_raw is not None and str(cost_raw).strip() != "" else None
    except (TypeError, ValueError):
        return jsonify({"message": "cost_pkr must be a number"}), 400
    rating_raw = data.get("rating")
    try:
        rating = float(rating_raw) if rating_raw is not None and str(rating_raw).strip() != "" else None
    except (TypeError, ValueError):
        return jsonify({"message": "rating must be a number"}), 400
    new_id = db.create_place(
        dest_id,
        name,
        category,
        main_type,
        lat,
        lon,
        description=(data.get("description") or "").strip() or None,
        cost_pkr=cost,
        rating=rating,
        address=(data.get("address") or "").strip() or None,
    )
    if not new_id:
        return jsonify({"message": "Could not create place (check main_type: hotel, restaurant, attraction)"}), 400
    return jsonify({"id": new_id, "ok": True}), 201


@app.route("/api/nlp/parse", methods=["POST"])
def nlp_parse():
    data = request.get_json() or {}
    text = (data.get("query") or data.get("text") or "").strip()
    user_id = data.get("user_id")
    extracted, nlp_source, groq_error = parse_travel_nlp(text, user_id)
    if user_id:
        try:
            db.save_search_query(int(user_id), text, extracted)
        except Exception:
            pass
    return jsonify(
        {
            "extracted": extracted,
            "ok": True,
            "nlp_source": nlp_source,
            "groq_error": groq_error,
        }
    )


@app.route("/api/search", methods=["POST"])
def search_dest():
    data = request.get_json() or {}
    text = (data.get("query") or "").strip()
    if not text:
        ex = {}
        nlp_source, groq_error = "empty", None
    else:
        ex, nlp_source, groq_error = parse_travel_nlp(text)
    max_b = (ex or {}).get("budget_pkr")
    region = (ex or {}).get("region")
    # Candidate pool: same budget / region (do not then ignore budget and return random rows)
    candidates = db.list_destinations(limit=300, region=region, max_budget_pkr=max_b)
    if not candidates and max_b is not None:
        candidates = db.list_destinations(limit=200, max_budget_pkr=int(max_b))
    ranked = select_destinations_for_search(
        candidates,
        ex,
        text,
        limit=24,
    )
    return jsonify(
        {
            "extracted": ex,
            "destinations": [enrich_card(d) for d in ranked],
            "nlp_source": nlp_source,
            "groq_error": groq_error,
        }
    )


def _profile_budget_pkr_hint(prof):
    if not prof:
        return None
    bmap = {"economy": 20000, "standard": 40000, "premium": 80000}
    return bmap.get((prof.get("budget_range") or "standard").lower(), 40000)


def _build_home_suggestions(prof, budget_hint_pkr):
    default_chips = [
        "Ideal weekend destinations this month in northern Pakistan",
        "Best budget trips under 20,000 PKR",
        "Top-rated adventure places near Islamabad",
    ]
    if not prof:
        return default_chips
    cats = [c.strip() for c in (prof.get("preferred_categories") or "").split(",") if c.strip()]
    if not cats:
        return default_chips
    c0, c1 = cats[0], cats[1] if len(cats) > 1 else None
    btxt = f" (~{int(budget_hint_pkr):,} PKR trip budget in mind)" if budget_hint_pkr else ""
    out = [
        f"Explore {c0} destinations in northern Pakistan",
        f"Top-rated {c0} getaways for your next trip" + btxt,
    ]
    if c1:
        out.append(f"Compare {c0} and {c1} — see what matches you best")
    else:
        out.append(f"More {c0} ideas hand-picked for your style")
    return out[:3]


@app.route("/api/home", methods=["GET"])
def home_feed():
    user_id = request.args.get("user_id", type=int)
    greeting = "Welcome to Smart Travel! Plan your next trip with AI."
    prof = db.get_profile(user_id) if user_id else None
    if user_id:
        u = db.get_user_by_id(user_id)
        if u:
            first = (u.get("full_name") or "Traveler").split()[0]
            greeting = f"Welcome back, {first}! Ready for your next adventure?"

    default_chips = [
        "Ideal weekend destinations this month in northern Pakistan",
        "Best budget trips under 20,000 PKR",
        "Top-rated adventure places near Islamabad",
    ]
    if user_id and prof:
        all_d = db.list_destinations(limit=200)
        enriched = [enrich_card(d) for d in all_d]
        merged_profile = {
            "preferred_travel_style": prof.get("preferred_travel_style"),
            "typical_trip_duration_days": prof.get("typical_trip_duration_days"),
            "budget_range": prof.get("budget_range"),
            "preferred_categories": prof.get("preferred_categories") or "",
        }
        ranked = run_recommendation(
            user_id, merged_profile, enriched, top_n=6
        )
        featured = [r["destination"] for r in ranked]
        budget_hint = _profile_budget_pkr_hint(prof)
        suggestions = _build_home_suggestions(prof, budget_hint)
    else:
        featured = [enrich_card(d) for d in db.list_destinations(limit=6)]
        suggestions = default_chips
    # Weather: RapidAPI Open Weather 13 (lat/lon) — default Islamabad
    weather = {
        "location": "Islamabad",
        "summary": "Pleasant, partly cloudy (set RAPIDAPI_KEY in .env for live data)",
        "temp_c": 28,
    }
    wlive = fetch_weather_latlon(33.6844, 73.0479, lang="EN")
    if wlive:
        weather = {
            "location": wlive.get("location") or "Islamabad",
            "summary": wlive.get("summary") or "",
            "temp_c": wlive.get("temp_c"),
            "feels_c": wlive.get("feels_c"),
            "humidity": wlive.get("humidity"),
            "wind_m_s": wlive.get("wind_m_s"),
            "source": wlive.get("source"),
        }

    travel_advisory = (
        "General advisory: check local road and weather conditions before travel to hilly areas."
    )

    pcats = []
    if prof and (prof.get("preferred_categories") or "").strip():
        pcats = [c.strip() for c in prof["preferred_categories"].split(",") if c.strip()]

    return jsonify(
        {
            "greeting": greeting,
            "featured": featured,
            "suggestions": suggestions,
            "featured_personalized": bool(user_id and prof),
            "preference_categories": pcats,
            "weather": weather,
            "travel_advisory": travel_advisory,
        }
    )


@app.route("/api/weather", methods=["GET"])
def weather_by_latlon():
    """Live conditions via RapidAPI Open Weather 13 (requires RAPIDAPI_KEY in .env)."""
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"ok": False, "message": "Query params lat and lon are required"}), 400
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        return jsonify({"ok": False, "message": "lat or lon out of range"}), 400
    lang = (request.args.get("lang") or "EN").strip() or "EN"
    w = fetch_weather_latlon(lat, lon, lang=lang)
    if not w:
        return jsonify(
            {
                "ok": False,
                "message": "Weather unavailable. Set RAPIDAPI_KEY in the backend .env and subscribe to the API on RapidAPI.",
            }
        ), 503
    return jsonify({**w, "ok": True})


@app.route("/api/recommendations/<int:user_id>", methods=["GET"])
def recommendations(user_id):
    u = db.get_user_by_id(user_id)
    if not u:
        return jsonify({"message": "User not found"}), 404
    prof = db.get_profile(user_id) or {}
    all_d = db.list_destinations(limit=200)
    merged_profile = {
        "preferred_travel_style": prof.get("preferred_travel_style"),
        "typical_trip_duration_days": prof.get("typical_trip_duration_days"),
        "budget_range": prof.get("budget_range"),
        "preferred_categories": prof.get("preferred_categories") or prof.get("preferred_travel_style"),
    }
    ranked = run_recommendation(
        user_id, merged_profile, [enrich_card(d) for d in all_d]
    )
    for r in ranked[:3]:
        d = r["destination"]
        try:
            did = int(d.get("db_id") or d.get("id"))
            db.store_recommendation(
                user_id, did, r["score"], r["reason"], "content_based"
            )
        except Exception:
            pass
    return jsonify({"items": ranked})


@app.route("/api/favorites/<int:user_id>", methods=["GET"])
def get_fav(user_id):
    ids = db.list_favorite_destination_ids(user_id)
    out = []
    for i in ids:
        d = db.get_destination_by_id(i)
        if d:
            out.append(enrich_card(d))
    return jsonify({"favorites": out})


@app.route("/api/favorites", methods=["POST"])
def post_fav():
    data = request.get_json() or {}
    user_id = int(data.get("user_id"))
    dest_id = data.get("destination_id")
    if not user_id or dest_id is None:
        return jsonify({"message": "user_id and destination_id required"}), 400
    is_on = db.toggle_favorite(user_id, dest_id)
    return jsonify({"saved": is_on})


@app.route("/api/trips", methods=["GET"])
def get_trips():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"message": "user_id required"}), 400
    raw = db.list_trips_for_user(user_id)
    for t in raw:
        _attach_trip_destination_image(t, keep_dest_coordinates=False)
    return jsonify({"trips": raw})


@app.route("/api/trips/<int:trip_id>", methods=["GET"])
def get_trip_detail(trip_id):
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"message": "user_id required"}), 400
    detail = db.get_trip_detail_for_user(int(user_id), int(trip_id))
    if not detail:
        return jsonify({"message": "Trip not found"}), 404
    if detail.get("trip"):
        t = detail["trip"]
        _attach_trip_destination_image(t, keep_dest_coordinates=True)
        did = t.get("destination_id")
        if did is not None:
            places = db.get_places_by_destination(int(did), limit=120) or []
            drow = {"latitude": t.get("latitude"), "longitude": t.get("longitude")}
            pts = collect_trip_map_points(detail.get("itinerary") or [], drow, places)
            murl = itinerary_map_image_url(pts, size="1200x520")
            if not murl and t.get("latitude") is not None and t.get("longitude") is not None:
                murl = destination_hero_image_url(t["latitude"], t["longitude"], size="1200x520")
            detail["map_image_url"] = murl
    return jsonify(detail)


def _build_trip_plan_dict(dest_id, days, total_budget_pkr, user_message, include_map_url=True):
    """
    Returns (payload_dict, None) or (None, error_message).
    No DB access beyond reads.
    """
    d = db.get_destination_by_id(int(dest_id))
    if not d or not d.get("name"):
        return None, "Invalid destination"
    did = d.get("db_id") or int(dest_id)
    places = db.get_places_by_destination(did, limit=120) or []
    b_int = int(total_budget_pkr) if total_budget_pkr is not None and str(total_budget_pkr) != "" else None
    msg = (user_message or "").strip()
    weather_snap = None
    wx = ""
    try:
        if d.get("latitude") is not None and d.get("longitude") is not None:
            weather_snap = fetch_weather_latlon(float(d["latitude"]), float(d["longitude"]), lang="EN")
    except (TypeError, ValueError):
        weather_snap = None
    if weather_snap:
        wx = format_weather_context_for_groq(weather_snap)

    if places:
        res = build_itinerary_from_places_with_groq(
            msg,
            d["name"],
            d.get("region"),
            int(days),
            b_int,
            d.get("category"),
            places,
            weather_context=wx,
            weather_snapshot=weather_snap,
        )
    else:
        res = build_itinerary_with_groq(
            d["name"],
            d.get("region"),
            int(days),
            b_int or d.get("cost"),
            d.get("category"),
            "[]",
            weather_context=wx,
            weather_snapshot=weather_snap,
        )
    itin = res["itinerary"]
    w_adv = res.get("weather_advisory")
    public_snap = None
    if weather_snap:
        public_snap = {k: v for k, v in weather_snap.items() if k not in ("source",)}
    est = sum_itinerary_cost_pkr(itin)
    if est <= 0:
        per_day = int(d.get("cost") or 5000) * int(days)
        est = int(total_budget_pkr) if total_budget_pkr else int(per_day * 0.4 + 5000 * int(days))
    map_url = None
    if include_map_url:
        map_pts = collect_trip_map_points(itin, d, places)
        map_url = itinerary_map_image_url(map_pts, size="1200x520")
        if not map_url and d.get("latitude") is not None and d.get("longitude") is not None:
            map_url = destination_hero_image_url(
                d.get("latitude"), d.get("longitude"), size="1200x520"
            )
    trip_meta = {
        "total_days": int(days),
        "hotel_nights": max(0, int(days) - 1),
        "label": f"{int(days)} day(s) · {max(0, int(days) - 1)} night(s) in {d['name']}",
    }
    return {
        "itinerary": itin,
        "destination_id": int(did),
        "estimated_total_pkr": est,
        "places_used_in_plan": len(places) > 0,
        "planner": "places_catalog_groq" if places else "destination_only_groq",
        "map_image_url": map_url,
        "trip_meta": trip_meta,
        "weather_advisory": w_adv,
        "weather_snapshot": public_snap,
    }, None


@app.route("/api/trips/preview", methods=["POST"])
def preview_trip():
    """Build AI itinerary only (no account, no database write). For trip page default view."""
    data = request.get_json() or {}
    dest_id = data.get("destination_id")
    if dest_id is None:
        return jsonify({"message": "destination_id required"}), 400
    days = int(data.get("days") or 3)
    budget = data.get("total_budget_pkr")
    user_message = (data.get("user_message") or data.get("query") or "").strip()
    b_int = int(budget) if budget is not None and str(budget) != "" else None
    out, err = _build_trip_plan_dict(
        int(dest_id), days, b_int, user_message, include_map_url=True
    )
    if err:
        return jsonify({"message": err}), 400
    return jsonify(out)


@app.route("/api/trips/plan", methods=["POST"])
def plan_trip():
    data = request.get_json() or {}
    user_id = int(data.get("user_id") or 0) or 0
    if not user_id:
        return jsonify({"message": "user_id required"}), 400
    dest_id = int(data.get("destination_id"))
    days = int(data.get("days") or 3)
    budget = data.get("total_budget_pkr")
    user_message = (data.get("user_message") or data.get("query") or "").strip()
    b_int = int(budget) if budget is not None and str(budget) != "" else None
    out, err = _build_trip_plan_dict(dest_id, days, b_int, user_message, include_map_url=True)
    if err or not out:
        return jsonify({"message": err or "Invalid destination"}), 400
    d = db.get_destination_by_id(dest_id)
    itin = out["itinerary"]
    est = out["estimated_total_pkr"]
    try:
        trip_id = db.create_trip_with_itinerary(
            user_id,
            d.get("db_id") or dest_id,
            f"Trip: {d['name']}",
            days,
            int(budget or est),
            est,
            itin,
        )
        db.log_activity(
            user_id, "trip_planned", "trip", trip_id, {"destination": d["name"]}
        )
    except Exception as e:
        return jsonify({"message": "Could not save trip", "error": str(e)}), 500
    return jsonify({**out, "trip_id": trip_id})


@app.route("/api/estimate", methods=["POST"])
def estimate():
    from cost.estimate import estimate_trip_cost

    data = request.get_json() or {}
    dest_id = data.get("destination_id")
    days = int(data.get("days") or 3)
    d = db.get_destination_by_id(dest_id) if dest_id is not None else None
    if not d:
        return jsonify({"message": "Need destination_id"}), 400
    c = estimate_trip_cost(d, days)
    return jsonify(c)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
