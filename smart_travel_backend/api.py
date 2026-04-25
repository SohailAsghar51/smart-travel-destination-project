import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash

import database_functions as db
import recommendation_logic
from config import (
    GOOGLE_MAPS_API_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    RAPIDAPI_KEY,
)
from weather_rapidapi import fetch_weather_latlon
from maps_util import (
    collect_itinerary_map_points,
    destination_hero_image_url,
    itinerary_map_image_url,
)
from weather_rapidapi import fetch_weather_latlon, format_weather_context_for_groq
from groq_client import (
    build_itinerary_from_places_with_groq,
    build_itinerary_with_groq,
    parse_travel_nlp,
    sum_itinerary_cost_pkr,
)
from search_helpers import select_destinations_for_search

app = Flask(__name__)
CORS(app)

# Thumbnails: prefer DB `image_url` in enrich_card; else Static Maps / defaults / per-name Unsplash
DEFAULT_DEST_IMAGE = (
    "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60"
)
DESTINATION_IMAGES = {
    "skardu": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60",
    "hunza": "https://images.unsplash.com/photo-1534949849017-ec5cfb6c7d2f?auto=format&fit=crop&w=1200&q=60",
    "murree": "https://images.unsplash.com/photo-1587502537745-4e39f3d5a6e0?auto=format&fit=crop&w=1200&q=60",
    "nathia": "https://images.unsplash.com/photo-1470770903676-69b98201ea1c?auto=format&fit=crop&w=1200&q=60",
    "islamabad": "https://images.unsplash.com/photo-1549880338-65ddcdfd017b?auto=format&fit=crop&w=1200&q=60",
    "naltar": "https://images.unsplash.com/photo-1504198453319-5ce911bafcde?auto=format&fit=crop&w=1200&q=60",
    "naran": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=60",
    "kaghan": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=60",
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
    # Accept simple form: styles array + budget (PKR) from the React app
    if not data:
        return {}
    styles = data.get("styles")
    if isinstance(styles, list) and len(styles) > 0:
        # Store as travel_style + categories list text
        travel_style = styles[0].lower()
        combined = ", ".join(styles)
    else:
        travel_style = data.get("preferred_travel_style")
        combined = data.get("preferred_categories")
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
    return {
        "preferred_travel_style": travel_style
        or data.get("preferred_travel_style")
        or "nature",
        "budget_range": br or "standard",
        "preferred_categories": combined or data.get("preferred_categories") or "nature",
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
            "google_maps_configured": bool(GOOGLE_MAPS_API_KEY),
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
            "styles": ["Nature"],
            "duration": 3,
        }
    st = (prof.get("preferred_travel_style") or "Nature").title()
    cats = (prof.get("preferred_categories") or prof.get("preferred_travel_style") or "")
    styles = [c.strip() for c in (cats or "").split(",") if c.strip()] or [st]
    bmap = {"economy": 20000, "standard": 40000, "premium": 80000}
    budget = bmap.get((prof.get("budget_range") or "standard").lower(), 20000)
    return {
        "budget": budget,
        "styles": [s[0].upper() + s[1:] if s else s for s in styles],
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
    return jsonify(
        {
            "message": "Login successful",
            "data": {
                "name": u["full_name"],
                "email": u["email"],
                "id": u["id"],
            },
            "user": user,
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


@app.route("/api/home", methods=["GET"])
def home_feed():
    user_id = request.args.get("user_id", type=int)
    greeting = "Welcome to Smart Travel! Plan your next trip with AI."
    if user_id:
        u = db.get_user_by_id(user_id)
        if u:
            first = (u.get("full_name") or "Traveler").split()[0]
            greeting = f"Welcome back, {first}! Ready for your next adventure?"

    featured = [enrich_card(d) for d in db.list_destinations(limit=6)]
    suggestions = [
        "Ideal weekend destinations this month in northern Pakistan",
        "Best budget trips under 20,000 PKR",
        "Top-rated adventure places near Islamabad",
    ]
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

    return jsonify(
        {
            "greeting": greeting,
            "featured": featured,
            "suggestions": suggestions,
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
    ranked = recommendation_logic.run_recommendation(
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
        _attach_trip_destination_image(detail["trip"], keep_dest_coordinates=True)
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
        map_pts = collect_itinerary_map_points(itin, d)
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
        int(dest_id), days, b_int, user_message, include_map_url=False
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
    from utils_cost import estimate_trip_cost

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
