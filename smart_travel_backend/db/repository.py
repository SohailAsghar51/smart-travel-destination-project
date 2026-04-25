"""
Database layer: all MySQL read/write for the Smart Travel app.

- The Flask API in api.py only calls these functions. It does not run SQL strings itself.
- Each function below opens a connection, does its job, then closes (simple style for a student project).
- Table names: users, user_profiles, destinations, places, trips, itineraries, etc.

Config (host, user, password, database name) comes from config.py and .env.
"""

import json
import re
import datetime
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME


# --- MySQL connection (one new connection per function call) ---

def create_database_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


# --- Users: sign up, sign in, load user row (no password in the dict we return) ---

def _row_to_user(row):
    """Turn one SQL result row (tuple) into a small dict for the API (for lists without password)."""
    if not row:
        return None
    return {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "auth_provider": row[3],
        "profile_picture_url": row[4],
    }


def create_user_email(full_name, email, password_plain):
    """Register: hash password, insert users row, and create an empty user_profiles row. Returns new user_id or None if email exists."""
    conn = create_database_connection()
    cursor = conn.cursor()
    ph = generate_password_hash(password_plain)
    q = (
        "INSERT INTO users (full_name, email, password_hash, auth_provider) "
        "VALUES (%s, %s, %s, 'email')"
    )
    try:
        cursor.execute(q, (full_name, email, ph))
        user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO user_profiles (user_id) VALUES (%s)", (user_id,)
        )
        conn.commit()
        return user_id
    except mysql.connector.IntegrityError:
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_by_email(email):
    """Load user for login: includes password_hash (caller must remove it before sending to the client)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, email, auth_provider, profile_picture_url, password_hash "
        "FROM users WHERE email = %s AND is_active = 1",
        (email,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        return None
    u = {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "auth_provider": row[3],
        "profile_picture_url": row[4],
        "password_hash": row[5],
    }
    return u


def verify_user_login(email, password_plain):
    """Check password. If correct, return user dict without password_hash. If wrong, return None."""
    u = get_user_by_email(email)
    if not u or not u.get("password_hash"):
        return None
    if not check_password_hash(u["password_hash"], password_plain):
        return None
    u.pop("password_hash", None)
    return u


def get_user_by_id(user_id):
    """User row for API (no password field). is_active=1 only."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, email, auth_provider, profile_picture_url FROM users "
        "WHERE id = %s AND is_active = 1",
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return _row_to_user(row)


# --- user_profiles: budget, travel style, saved category list, etc. ---

def get_profile(user_id):
    """Read one row from user_profiles (travel preferences for recommendations)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, preferred_travel_style, budget_range, preferred_regions, "
        "preferred_categories, typical_trip_duration_days, preferred_currency "
        "FROM user_profiles WHERE user_id = %s",
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "preferred_travel_style": row[2],
        "budget_range": row[3],
        "preferred_regions": row[4] or "",
        "preferred_categories": row[5] or "",
        "typical_trip_duration_days": row[6] or 3,
        "preferred_currency": row[7] or "PKR",
    }


def update_profile(
    user_id,
    preferred_travel_style=None,
    budget_range=None,
    preferred_regions=None,
    preferred_categories=None,
    typical_trip_duration_days=None,
    preferred_currency=None,
):
    """Change only the fields you pass (not None). If nothing to update, we just return the current profile."""
    conn = create_database_connection()
    cursor = conn.cursor()
    parts = []
    values = []
    if preferred_travel_style is not None:
        parts.append("preferred_travel_style = %s")
        values.append(preferred_travel_style)
    if budget_range is not None:
        parts.append("budget_range = %s")
        values.append(budget_range)
    if preferred_regions is not None:
        parts.append("preferred_regions = %s")
        values.append(preferred_regions)
    if preferred_categories is not None:
        parts.append("preferred_categories = %s")
        values.append(preferred_categories)
    if typical_trip_duration_days is not None:
        parts.append("typical_trip_duration_days = %s")
        values.append(int(typical_trip_duration_days))
    if preferred_currency is not None:
        parts.append("preferred_currency = %s")
        values.append(preferred_currency)
    if not parts:
        cursor.close()
        conn.close()
        return get_profile(user_id)
    values.append(user_id)
    q = "UPDATE user_profiles SET " + ", ".join(parts) + " WHERE user_id = %s"
    cursor.execute(q, tuple(values))
    conn.commit()
    cursor.close()
    conn.close()
    return get_profile(user_id)


# --- Destinations (places to visit) and their picture URL ---

# Column order must match destination_row_to_dict() below (id, name, country, region, … image_url, is_active)
_DEST_SELECT = (
    "id, name, country, region, category, description, avg_cost_pkr, "
    "best_season, climate, safety_rating, rating, popularity_score, latitude, longitude, image_url, is_active"
)


def destination_row_to_dict(row):
    """Convert one SELECT result from `destinations` into the JSON shape the React app expects."""
    img = ""
    if len(row) > 14 and row[14] is not None:
        img = str(row[14]).strip()
    return {
        "id": str(row[0]),
        "db_id": row[0],
        "name": row[1],
        "region": row[3] or "",
        "category": row[4] or "",
        "type": row[4] or "",
        "description": row[5] or "",
        "cost": int(row[6]) if row[6] is not None else 0,
        "priceFrom": int(row[6]) if row[6] is not None else 0,
        "best_season": row[7] or "",
        "user_rating": float(row[10]) if row[10] is not None else 0,
        "rating": float(row[10]) if row[10] is not None else 0,
        "latitude": float(row[12]) if row[12] is not None else 0,
        "longitude": float(row[13]) if row[13] is not None else 0,
        "safety_rating": float(row[9]) if row[9] is not None else 0,
        "image_url": img or None,
    }


def list_destination_categories():
    """All different category words in the table (for filter checkboxes). Lowercase, sorted."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT LOWER(TRIM(category)) AS c FROM destinations "
        "WHERE is_active = 1 AND TRIM(COALESCE(category, '')) != '' ORDER BY c"
    )
    rows = [r[0] for r in cursor.fetchall() if r and r[0]]
    cursor.close()
    conn.close()
    return rows


def list_destinations(limit=100, region=None, max_budget_pkr=None):
    """Many destination rows. Optional: filter by region text and/or max daily cost (PKR)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    if region and max_budget_pkr is not None:
        q = (
            f"SELECT {_DEST_SELECT} "
            "FROM destinations WHERE is_active = 1 AND region LIKE %s AND avg_cost_pkr <= %s "
            "ORDER BY rating DESC, popularity_score DESC LIMIT %s"
        )
        cursor.execute(q, (f"%{region}%", int(max_budget_pkr), int(limit)))
    elif region:
        q = (
            f"SELECT {_DEST_SELECT} "
            "FROM destinations WHERE is_active = 1 AND region LIKE %s "
            "ORDER BY rating DESC, popularity_score DESC LIMIT %s"
        )
        cursor.execute(q, (f"%{region}%", int(limit)))
    elif max_budget_pkr is not None:
        q = (
            f"SELECT {_DEST_SELECT} "
            "FROM destinations WHERE is_active = 1 AND avg_cost_pkr <= %s "
            "ORDER BY rating DESC, popularity_score DESC LIMIT %s"
        )
        cursor.execute(q, (int(max_budget_pkr), int(limit)))
    else:
        q = (
            f"SELECT {_DEST_SELECT} "
            "FROM destinations WHERE is_active = 1 "
            "ORDER BY rating DESC, popularity_score DESC LIMIT %s"
        )
        cursor.execute(q, (int(limit),))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [destination_row_to_dict(r) for r in rows]


def get_destination_by_id(dest_id):
    """One destination by primary key, or None if missing / not active."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT {_DEST_SELECT} FROM destinations WHERE id = %s AND is_active = 1",
        (int(dest_id),),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        return None
    return destination_row_to_dict(row)


# --- Search history and “for you” scoring (optional logging) ---

def save_search_query(
    user_id,
    raw_query,
    extracted,
):
    """Save what the user typed and what the AI extracted (for analytics / future use)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    ent = json.dumps(extracted)
    q = (
        "INSERT INTO search_queries (user_id, raw_query, extracted_intent, "
        "destination_name, extracted_budget_pkr, extracted_duration_days, "
        "extracted_travel_style, extracted_entities) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    cursor.execute(
        q,
        (
            user_id,
            raw_query,
            extracted.get("intent"),
            extracted.get("destination") or extracted.get("region"),
            extracted.get("budget_pkr"),
            extracted.get("duration_days"),
            extracted.get("travel_style"),
            ent,
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()


def store_recommendation(user_id, destination_id, score, reason, algorithm_used):
    """Insert one recommendation row (used when we show top picks to a user)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recommendations (user_id, destination_id, recommendation_score, "
        "recommendation_reason, algorithm_used) VALUES (%s, %s, %s, %s, %s)",
        (user_id, int(destination_id), float(score), reason, algorithm_used),
    )
    conn.commit()
    cursor.close()
    conn.close()


# --- Saved “heart” destinations for a user ---

def list_favorite_destination_ids(user_id):
    """List of destination_id values the user saved (newest first)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT destination_id FROM favorite_destinations WHERE user_id = %s ORDER BY added_at DESC",
        (user_id,),
    )
    rows = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


def toggle_favorite(user_id, destination_id):
    """If the pair (user, place) exists, delete it; else insert. Returns True if now saved, False if removed."""
    conn = create_database_connection()
    cursor = conn.cursor()
    dest_id = int(destination_id)
    cursor.execute(
        "SELECT 1 FROM favorite_destinations WHERE user_id = %s AND destination_id = %s",
        (user_id, dest_id),
    )
    if cursor.fetchone():
        cursor.execute(
            "DELETE FROM favorite_destinations WHERE user_id = %s AND destination_id = %s",
            (user_id, dest_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return False
    cursor.execute(
        "INSERT INTO favorite_destinations (user_id, destination_id) VALUES (%s, %s)",
        (user_id, dest_id),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True


# --- Trips: saved travel plans (header row + cost + days/items in other functions) ---

def list_trips_for_user(user_id):
    """Short list of trips for one user, with destination name/region/photo for the UI list."""
    conn = create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT t.id, t.title, t.destination_id, t.duration_days, t.total_budget_pkr, t.estimated_cost_pkr, t.trip_status, "
        "d.name, d.region, d.image_url, d.latitude, d.longitude FROM trips t "
        "LEFT JOIN destinations d ON t.destination_id = d.id "
        "WHERE t.user_id = %s ORDER BY t.created_at DESC",
        (user_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    out = []
    for r in rows:
        dlat, dlng = None, None
        if len(r) > 10 and r[10] is not None:
            try:
                dlat = float(r[10])
            except (TypeError, ValueError):
                pass
        if len(r) > 11 and r[11] is not None:
            try:
                dlng = float(r[11])
            except (TypeError, ValueError):
                pass
        img = ""
        if len(r) > 9 and r[9] is not None:
            img = str(r[9]).strip()
        out.append(
            {
                "id": r[0],
                "title": r[1],
                "destination_id": r[2],
                "duration_days": r[3],
                "total_budget_pkr": r[4],
                "estimated_cost_pkr": r[5],
                "trip_status": r[6],
                "destination_name": r[7] or "Unknown",
                "region": (r[8] or "") if len(r) > 8 else "",
                "image_url": img or None,
                "dest_latitude": dlat,
                "dest_longitude": dlng,
            }
        )
    return out


def _format_time_for_json(t):
    """Change MySQL TIME to a short time string (HH:MM) for the JSON we send to React."""
    if t is None:
        return None
    if isinstance(t, datetime.timedelta):
        secs = int(t.total_seconds()) % 86400
        h, r = divmod(secs, 3600)
        m, _ = divmod(r, 60)
        return f"{h:02d}:{m:02d}"
    if isinstance(t, datetime.time):
        return t.strftime("%H:%M")
    s = str(t)
    if len(s) >= 5 and s[2] == ":":
        return s[:5]
    return s[:8] if s else None


def get_trip_detail_for_user(user_id, trip_id):
    """
    One full saved trip: header, optional cost table, and each day with lines (stops) inside.
    The user_id check makes sure you cannot read another person’s trip.
    """
    conn = create_database_connection()
    cursor = conn.cursor()
    try:
        # 1) Trip + destination info (one row)
        cursor.execute(
            "SELECT t.id, t.title, t.destination_id, t.duration_days, t.total_budget_pkr, t.estimated_cost_pkr, "
            "t.trip_status, d.name, d.region, d.image_url, d.latitude, d.longitude FROM trips t "
            "LEFT JOIN destinations d ON t.destination_id = d.id "
            "WHERE t.id = %s AND t.user_id = %s",
            (int(trip_id), int(user_id)),
        )
        row = cursor.fetchone()
        if not row:
            return None
        dlat, dlng = None, None
        if len(row) > 10 and row[10] is not None:
            try:
                dlat = float(row[10])
            except (TypeError, ValueError):
                pass
        if len(row) > 11 and row[11] is not None:
            try:
                dlng = float(row[11])
            except (TypeError, ValueError):
                pass
        img = ""
        if len(row) > 9 and row[9] is not None:
            img = str(row[9]).strip()
        trip = {
            "id": row[0],
            "title": row[1],
            "destination_id": row[2],
            "duration_days": row[3],
            "total_budget_pkr": int(row[4] or 0) if row[4] is not None else None,
            "estimated_cost_pkr": int(row[5] or 0) if row[5] is not None else 0,
            "trip_status": row[6] or "planned",
            "destination_name": row[7] or "Unknown",
            "region": row[8] or "",
            "image_url": img or None,
            "dest_latitude": dlat,
            "dest_longitude": dlng,
        }
        ddays = int(trip["duration_days"] or 0)
        trip_meta = {
            "total_days": ddays,
            "hotel_nights": max(0, ddays - 1),
            "label": f"{ddays} day(s) · {max(0, ddays - 1)} night(s) — saved plan",
        }

        # 2) One optional row: how cost was split (transport, hotel, food, …)
        cursor.execute(
            "SELECT transport_cost_pkr, accommodation_cost_pkr, food_cost_pkr, activities_cost_pkr, total_estimated_cost_pkr "
            "FROM trip_cost_breakdown WHERE trip_id = %s",
            (int(trip_id),),
        )
        br = cursor.fetchone()
        cost_breakdown = None
        if br:
            cost_breakdown = {
                "transport_cost_pkr": int(br[0] or 0),
                "accommodation_cost_pkr": int(br[1] or 0),
                "food_cost_pkr": int(br[2] or 0),
                "activities_cost_pkr": int(br[3] or 0),
                "total_estimated_cost_pkr": int(br[4] or 0),
            }

        # 3) For each day: one itinerary row, then all items (lines) with optional place name
        cursor.execute(
            "SELECT id, day_number, estimated_day_cost_pkr, notes FROM itineraries WHERE trip_id = %s ORDER BY day_number",
            (int(trip_id),),
        )
        day_rows = cursor.fetchall()
        days_out = []
        for dr in day_rows:
            itin_id, day_num, day_est, day_notes = dr[0], dr[1], dr[2], dr[3]
            cursor.execute(
                "SELECT ii.place_id, ii.item_type, ii.title, ii.description, ii.start_time, ii.end_time, "
                "ii.sequence_number, ii.estimated_cost_pkr, ii.latitude, ii.longitude, p.address, p.name "
                "FROM itinerary_items ii "
                "LEFT JOIN places p ON p.id = ii.place_id "
                "WHERE ii.itinerary_id = %s ORDER BY ii.sequence_number",
                (itin_id,),
            )
            items = []
            for ir in cursor.fetchall():
                lat = ir[8]
                lon = ir[9]
                try:
                    lat_f = float(lat) if lat is not None else None
                except (TypeError, ValueError):
                    lat_f = None
                try:
                    lon_f = float(lon) if lon is not None else None
                except (TypeError, ValueError):
                    lon_f = None
                addr = (ir[10] or "").strip()
                it = {
                    "place_id": ir[0],
                    "item_type": (ir[1] or "attraction").lower(),
                    "title": ir[2] or "",
                    "description": ir[3] or "",
                    "start_time": _format_time_for_json(ir[4]),
                    "end_time": _format_time_for_json(ir[5]),
                    "sequence_number": int(ir[6] or 0),
                    "estimated_cost_pkr": int(ir[7] or 0),
                    "latitude": lat_f,
                    "longitude": lon_f,
                }
                if addr:
                    it["place_address"] = addr
                if ir[11]:
                    it["place_name"] = ir[11]
                items.append(it)
            day_entry = {
                "day_number": int(day_num),
                "day_title": None,
                "day_summary": (day_notes or "").strip() or None,
                "estimated_day_cost_pkr": int(day_est or 0),
                "items": items,
            }
            days_out.append(day_entry)
        return {
            "trip": trip,
            "cost_breakdown": cost_breakdown,
            "itinerary": days_out,
            "trip_meta": trip_meta,
        }
    finally:
        cursor.close()
        conn.close()


# --- User activity log (optional: “user X saved a trip”) ---

def log_activity(user_id, activity_type, entity_type=None, entity_id=None, metadata=None):
    """Insert one line into user_activity. metadata is a small dict, stored as JSON text."""
    conn = create_database_connection()
    cursor = conn.cursor()
    meta = json.dumps(metadata) if metadata is not None else None
    cursor.execute(
        "INSERT INTO user_activity (user_id, activity_type, entity_type, entity_id, metadata) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, activity_type, entity_type, entity_id, meta),
    )
    conn.commit()
    cursor.close()
    conn.close()


# --- Admin-style edit of a destination (only the fields you pass) ---

def update_destination(
    dest_id,
    name=None,
    region=None,
    category=None,
    description=None,
    avg_cost_pkr=None,
    best_season=None,
    rating=None,
    popularity_score=None,
    safety_rating=None,
    latitude=None,
    longitude=None,
):
    """Update destinations row by id. Only non-None arguments are written."""
    conn = create_database_connection()
    cursor = conn.cursor()
    parts = []
    values = []
    if name is not None:
        parts.append("name = %s")
        values.append(name)
    if region is not None:
        parts.append("region = %s")
        values.append(region)
    if category is not None:
        parts.append("category = %s")
        values.append(category)
    if description is not None:
        parts.append("description = %s")
        values.append(description)
    if avg_cost_pkr is not None:
        parts.append("avg_cost_pkr = %s")
        values.append(int(avg_cost_pkr))
    if best_season is not None:
        parts.append("best_season = %s")
        values.append(best_season)
    if rating is not None:
        parts.append("rating = %s")
        values.append(float(rating))
    if popularity_score is not None:
        parts.append("popularity_score = %s")
        values.append(float(popularity_score))
    if safety_rating is not None:
        parts.append("safety_rating = %s")
        values.append(float(safety_rating))
    if latitude is not None:
        parts.append("latitude = %s")
        values.append(float(latitude))
    if longitude is not None:
        parts.append("longitude = %s")
        values.append(float(longitude))
    if not parts:
        cursor.close()
        conn.close()
        return
    values.append(int(dest_id))
    q = "UPDATE destinations SET " + ", ".join(parts) + " WHERE id = %s"
    cursor.execute(q, tuple(values))
    conn.commit()
    cursor.close()
    conn.close()


# --- POIs: hotels, restaurants, … linked to a destination_id ---

def get_places_by_destination(dest_id, main_type=None, limit=100):
    """All active places in one destination. If main_type is set, only that type (hotel, …)."""
    conn = create_database_connection()
    cursor = conn.cursor()
    if main_type:
        cursor.execute(
            "SELECT id, name, category, main_type, cost_pkr, rating, latitude, longitude, address "
            "FROM places WHERE destination_id = %s AND is_active = 1 AND main_type = %s "
            "ORDER BY rating DESC LIMIT %s",
            (int(dest_id), main_type, int(limit)),
        )
    else:
        cursor.execute(
            "SELECT id, name, category, main_type, cost_pkr, rating, latitude, longitude, address "
            "FROM places WHERE destination_id = %s AND is_active = 1 "
            "ORDER BY main_type, rating DESC LIMIT %s",
            (int(dest_id), int(limit)),
        )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "category": r[2],
            "main_type": r[3],
            "cost_pkr": r[4],
            "rating": float(r[5]) if r[5] is not None else None,
            "latitude": float(r[6]) if r[6] is not None else None,
            "longitude": float(r[7]) if r[7] is not None else None,
            "address": r[8] or "",
        }
        for r in rows
    ]


def _sql_time_value(s):
    """Turn a time string from the AI/JSON into a value MySQL TIME column accepts, or None."""
    if s is None or s == "":
        return None
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
    if m:
        h, mi, se = m.group(1), m.group(2), m.group(3) or "00"
        return f"{int(h):02d}:{int(mi):02d}:{int(se):02d}"
    m2 = re.match(
        r"^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$",
        s.replace(".", "").strip(),
    )
    if m2:
        h, ap = int(m2.group(1)), m2.group(3).lower()
        mi = m2.group(2)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mi}:00"
    return None


def create_trip_with_itinerary(
    user_id,
    destination_id,
    title,
    duration_days,
    total_budget_pkr,
    estimated_cost_pkr,
    day_plans,
):
    """
    Big save: one row in `trips`, one row per day in `itineraries`, many rows in `itinerary_items`.
    `day_plans` is a list like:
      { day_number, items: [ { start_time, end_time, item_type, title, cost, lat/lon, ... }, ... ] }
    We also build trip_cost_breakdown from item types. On any error, we rollback the whole thing.
    """
    conn = create_database_connection()
    cursor = conn.cursor()
    try:
        # Parent row in `trips`
        cursor.execute(
            "INSERT INTO trips (user_id, destination_id, title, duration_days, total_budget_pkr, estimated_cost_pkr, trip_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'planned')",
            (user_id, int(destination_id), title, int(duration_days), total_budget_pkr, estimated_cost_pkr),
        )
        trip_id = cursor.lastrowid

        t_transport = 0
        t_food = 0
        t_hotel = 0
        t_act = 0

        for day in day_plans:  # each day: sum cost by type, then save items
            day_no = int(day["day_number"])
            day_cost = 0
            for it in day.get("items", []):
                c = int(it.get("estimated_cost_pkr") or 0)
                day_cost += c
                mt = (it.get("item_type") or "attraction").lower()
                if mt == "transport":
                    t_transport += c
                elif mt == "restaurant":
                    t_food += c
                elif mt == "hotel":
                    t_hotel += c
                else:
                    t_act += c

            cursor.execute(
                "INSERT INTO itineraries (trip_id, day_number, estimated_day_cost_pkr) VALUES (%s, %s, %s)",
                (trip_id, day_no, day_cost),
            )
            itin_id = cursor.lastrowid
            for it in day.get("items", []):
                st = _sql_time_value(it.get("start_time"))
                et = _sql_time_value(it.get("end_time"))
                lat = it.get("latitude")
                lon = it.get("longitude")
                try:
                    lat_f = float(lat) if lat is not None and lat != "" else None
                except (TypeError, ValueError):
                    lat_f = None
                try:
                    lon_f = float(lon) if lon is not None and lon != "" else None
                except (TypeError, ValueError):
                    lon_f = None
                cursor.execute(
                    "INSERT INTO itinerary_items (itinerary_id, place_id, item_type, title, description, "
                    "start_time, end_time, sequence_number, estimated_cost_pkr, latitude, longitude) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        itin_id,
                        it.get("place_id"),
                        it.get("item_type") or "attraction",
                        it.get("title") or "Activity",
                        it.get("description") or "",
                        st,
                        et,
                        int(it.get("sequence_number") or 0),
                        int(it.get("estimated_cost_pkr") or 0),
                        lat_f,
                        lon_f,
                    ),
                )

        total_est = t_transport + t_food + t_hotel + t_act
        if total_est == 0 and estimated_cost_pkr:
            total_est = int(estimated_cost_pkr)
        # One summary row: money by category (note: t_hotel goes to accommodation in the table)
        cursor.execute(
            "INSERT INTO trip_cost_breakdown (trip_id, transport_cost_pkr, accommodation_cost_pkr, food_cost_pkr, "
            "activities_cost_pkr, total_estimated_cost_pkr) VALUES (%s, %s, %s, %s, %s, %s)",
            (trip_id, t_transport, t_hotel, t_food, t_act, total_est),
        )
        cursor.execute("UPDATE trips SET estimated_cost_pkr = %s WHERE id = %s", (total_est, trip_id))
        conn.commit()
        return trip_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
