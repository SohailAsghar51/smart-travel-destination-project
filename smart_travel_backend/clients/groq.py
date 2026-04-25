"""
Groq client (OpenAI-compatible Chat Completions at api.groq.com).

The Flask app (api.py) calls this module. Nothing here touches MySQL; it only
talks to Groq and returns dicts the API layer can store or return as JSON.

================================================================================
END-TO-END FLOWS (read top to bottom for each use case)
================================================================================

(1) SEARCH / HOME — "What does the user mean?"

    User types a sentence in the UI
         │
         ▼
    api.py  →  parse_travel_nlp(text, user_id)
         │
         ├─ No GROQ_API_KEY?
         │     → _fallback_parse(text)  (regex: days, budget, region, "trip to X")
         │     → _normalize_nlp_result(...)
         │     → return (dict, "unconfigured", error_message)
         │
         └─ Key present: POST to Groq with _NLP_SYSTEM + user text
                 │
                 ├─ HTTP error / bad response / JSON parse fail?
                 │     → same fallback as above, return nlp_source="fallback"
                 │
                 └─ OK → _parse_json_object_from_text(assistant string)
                        → _normalize_nlp_result(dict)  (ints, defaults)
                        → return (dict, "groq", None)

(2) TRIP PREVIEW (no place rows) — "Build a day-by-day plan from a destination"

    api.py  →  build_itinerary_with_groq(..., places_context, weather_...)
         │
         ├─ No GROQ_API_KEY?
         │     → _simple_rule_itinerary(...)  (toy 2 items/day, weather hint in day 1)
         │     → _itinerary_result(..., _normalize_weather_advisory)
         │
         └─ Build messages: _system_destination_only(weather) + user blob
                 (optional CURRENT WEATHER + optional "place ideas" text)
                 │
                 → _groq_post_chat(..., json_object=True)
                 → _parse_json_object_from_text → { days, weather_advisory }
                 → _normalize_weather_advisory(...)
                 → _days_from_groq_obj(obj, with_place_id=False)  (no place_id on items)
                 │
                 If anything fails or days empty
                 → fall back to _simple_rule_itinerary + default advisory

(3) TRIP WITH DB PLACES — "Only use real hotels/restaurants from our catalog"

    api.py  →  build_itinerary_from_places_with_groq(..., places_list, ...)
         │
         ├─ No key OR empty places_list?
         │     → delegate to (2) with str(places) as context
         │
         ├─ _catalog_json(places_list)  (first 80 rows, id, name, type, cost, lat, lon, address)
         ├─ Messages: _system_places(weather) + USER_MESSAGE + CATALOG json
         │
         → _groq_post_chat (longer timeout 90s)
         → parse JSON → weather_advisory + days with place_id on items
         → _days_from_groq_obj(obj, with_place_id=True)
         → _validate_itinerary_place_ids(days, places_list)
                 (drop bad ids, fill title/cost/lat/lon/address from DB rows)
         │
         If Groq fails or days empty
         → build_itinerary_with_groq(..., cj[:2000], ...)  # simpler planner, catalog snippet

(4) Helpers used everywhere

    _groq_post_chat  →  POST { model, messages, temperature, optional response_format }
                      →  if 400/404/422 with json mode, retry without response_format
    _parse_json_object_from_text  →  strip ```json fences, then json.loads, or slice first {...}
    _hhmm  →  normalize "9:30" / "9:30 AM" style times for itinerary items
================================================================================
"""

import json
import logging
import re

import requests

from config import GROQ_API_KEY, GROQ_MODEL
from clients.weather import weather_planning_severity

_log = logging.getLogger(__name__)
# Same endpoint as OpenAI; auth uses GROQ_API_KEY in the Authorization header.
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ---------------------------------------------------------------------------
# System prompts & shared utilities (time parse, item types, HTTP, JSON text)
# ---------------------------------------------------------------------------

_NLP_SYSTEM = (
    "You extract travel planning parameters from the user's message. "
    "Output a single JSON object only (no markdown, no text before or after). "
    "Keys: intent (one of: travel_planning, search, budget_check), "
    "destination (string or null), duration_days (integer or null), budget_pkr (integer or null), "
    "travel_style (one of: adventure, relaxation, culture, family, nature, luxury, or null), "
    "region (string or null), activity_hint (string or null). "
    "All numbers must be plain integers, not strings."
)

def _hhmm(s):
    """Convert model time strings to 'HH:MM' for the DB, or None."""
    if s is None or s == "":
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _item_type(s):
    # DB itinerary_items + places enforce these four; anything else becomes attraction.
    t = (s or "attraction").lower()
    return t if t in ("hotel", "restaurant", "attraction", "transport") else "attraction"


def _itinerary_result(itin, weather_advisory=None):
    """Shape returned to api.py: list of day dicts + optional weather notes."""
    return {"itinerary": itin, "weather_advisory": weather_advisory}


def _normalize_weather_advisory(raw, weather_snapshot=None):
    """Coerce model (or None) into {summary, adjustments, reschedule_suggestion, severity}."""
    fb = weather_planning_severity(weather_snapshot) if weather_snapshot else "ok"
    if not isinstance(raw, dict):
        return {
            "summary": "Current weather was considered when building this plan (see day notes).",
            "adjustments": "",
            "reschedule_suggestion": None,
            "severity": fb,
        }
    sev = raw.get("severity") or fb
    if sev not in ("ok", "caution", "consider_rescheduling"):
        sev = fb
    return {
        "summary": (raw.get("summary") or "")[:800],
        "adjustments": (raw.get("adjustments") or raw.get("adjustments_made") or "")[:2000],
        "reschedule_suggestion": raw.get("reschedule_suggestion"),
        "severity": sev,
    }


def _parse_json_object_from_text(content):
    """Model output may have markdown fences or text before the JSON object."""
    s = (content or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("{"), s.rfind("}")
        if i != -1 and j > i:
            return json.loads(s[i : j + 1])
        raise


def _groq_post_chat(messages, temperature, json_object, timeout=60):
    """One chat-completions call. If json mode fails (some models), retry without it."""
    body = {"model": GROQ_MODEL, "messages": messages, "temperature": temperature}
    if json_object:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    if not r.ok and json_object and r.status_code in (400, 404, 422):
        _log.info("Retrying Groq without response_format (status %s)", r.status_code)
        return _groq_post_chat(messages, temperature, False, timeout=timeout)
    return r


def _groq_json_content(r):
    """Assistant message text (may be JSON) from a successful response object."""
    return r.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Itinerary: normalize model "days" / "items" (used by both planner variants)
# ---------------------------------------------------------------------------

def _norm_groq_item(it, i, with_place_id):
    """One day line item. Catalog planner sets with_place_id=True to keep place_id."""
    it = it or {}
    t = _item_type(it.get("item_type"))
    dflt = "Activity" if with_place_id else "Visit"
    row = {
        "item_type": t,
        "title": (it.get("title") or dflt)[:200],
        "description": (it.get("description") or "")[:2000],
        "start_time": _hhmm(it.get("start_time")),
        "end_time": _hhmm(it.get("end_time")),
        "sequence_number": int(it.get("sequence_number") or (i + 1)),
        "estimated_cost_pkr": int(it.get("estimated_cost_pkr") or 0),
    }
    if with_place_id:
        row["place_id"] = it.get("place_id")
    return row


def _days_from_groq_obj(obj, with_place_id):
    """Turn model JSON (days/items) into our cleaned list. `with_place_id` keeps place_id on each item."""
    out = []
    for d in obj.get("days") or []:
        items = d.get("items") or []
        clean = [_norm_groq_item(x, j, with_place_id) for j, x in enumerate(items)]
        out.append(
            {
                "day_number": int(d.get("day_number") or len(out) + 1),
                "day_title": (d.get("day_title") or d.get("title") or "")[:200] or None,
                "day_summary": (
                    (d.get("day_summary") or d.get("day_focus") or d.get("notes") or "")[:1500] or None
                ),
                "items": clean,
            }
        )
    return out


# ---------------------------------------------------------------------------
# NLP: parse_travel_nlp  (see module docstring flow 1)
# ---------------------------------------------------------------------------

def _fallback_parse(text):
    """When Groq is off or failed: cheap regex to guess days, budget, region, style."""
    t = (text or "").lower()
    out = {
        "intent": "travel_planning",
        "destination": None,
        "duration_days": None,
        "budget_pkr": None,
        "travel_style": None,
        "region": None,
        "activity_hint": None,
    }
    m = re.search(r"(\d+)\s*-?\s*day", t) or re.search(r"for\s+(\d+)\s*day", t)
    if m:
        out["duration_days"] = int(m.group(1))
    b = re.search(r"under\s+([\d,]+)\s*(?:pkr|rs|rupees?)?", t) or re.search(
        r"(\d{4,})\s*(?:pkr|rs)?", t
    )
    if b:
        out["budget_pkr"] = int(b.group(1).replace(",", ""))
    if "naran" in t or "northern" in t or "north" in t:
        out["region"] = "Khyber Pakhtunkhwa" if "kpk" in t or "naran" in t else "Northern"
    to_m = re.search(
        r"(?:trip|travel)\s+to\s+([a-z\s]+?)(?:\s+under|\s+for|\s+in|\.|\s*$)", t
    )
    if to_m:
        out["destination"] = to_m.group(1).strip().title()[:100]
    if "adventure" in t or "hiking" in t:
        out["travel_style"] = "adventure"
    elif "relax" in t or "beach" in t:
        out["travel_style"] = "relaxation"
    elif "culture" in t or "historical" in t:
        out["travel_style"] = "culture"
    return out


def _normalize_nlp_result(obj, _original_text):
    """One canonical dict for search/recommend code; ints for duration and budget when possible."""
    if not isinstance(obj, dict):
        obj = {}
    out = {
        "intent": obj.get("intent") or "travel_planning",
        "destination": obj.get("destination"),
        "duration_days": obj.get("duration_days"),
        "budget_pkr": obj.get("budget_pkr"),
        "travel_style": obj.get("travel_style"),
        "region": obj.get("region"),
        "activity_hint": obj.get("activity_hint"),
    }
    for key in ("duration_days", "budget_pkr"):
        v = out[key]
        if v is not None:
            try:
                out[key] = int(v)
            except (TypeError, ValueError):
                out[key] = None
    return out


def parse_travel_nlp(text, user_id=None):
    """
    Returns (extracted_dict, nlp_source, error_or_none).
    nlp_source: "groq" | "unconfigured" | "fallback" — see module docstring flow (1).

    user_id is accepted for a future "personalized prompt" but is not used yet.
    """
    if not GROQ_API_KEY:
        return (
            _normalize_nlp_result(_fallback_parse(text), text),
            "unconfigured",
            "GROQ_API_KEY is not set in environment or .env (see smart_travel_backend/.env)",
        )

    err_note = None
    try:
        r = _groq_post_chat(
            [
                {"role": "system", "content": _NLP_SYSTEM},
                {"role": "user", "content": text or ""},
            ],
            temperature=0.1,
            json_object=True,
        )
        if not r.ok:
            err_note = f"HTTP {r.status_code}: {(r.text or '')[:500]}"
            _log.warning("Groq NLP HTTP error: %s", err_note)
            return _normalize_nlp_result(_fallback_parse(text), text), "fallback", err_note

        content = _groq_json_content(r)
        try:
            obj = _parse_json_object_from_text(content)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            err_note = f"JSON parse: {e}"
            _log.warning("Groq NLP JSON error: %s; content=%.200r", err_note, content)
            return _normalize_nlp_result(_fallback_parse(text), text), "fallback", err_note
        return _normalize_nlp_result(obj, text), "groq", None
    except requests.RequestException as e:
        err_note = str(e)[:500]
        _log.warning("Groq NLP request error: %s", err_note)
    except (KeyError, IndexError) as e:
        err_note = f"Response shape: {e}"
        _log.warning("Groq NLP response error: %s", err_note)
    except Exception as e:  # noqa: BLE001
        err_note = str(e)[:500]
        _log.warning("Groq NLP error: %s", err_note)

    # Any exception path above: same shape as HTTP/JSON failure
    return _normalize_nlp_result(_fallback_parse(text), text), "fallback", err_note


def parse_travel_query_with_groq(text, user_id=None):
    """Same as parse_travel_nlp but returns only the dict (old callers)."""
    d, _src, _err = parse_travel_nlp(text, user_id)
    return d


# ---------------------------------------------------------------------------
# Itinerary without place IDs — build_itinerary_with_groq  (module flow 2)
# ---------------------------------------------------------------------------

def _system_destination_only(weather_context):
    w_extra = (
        "When CURRENT WEATHER is provided, you MUST: (1) Prefer indoor or covered activities, museums, and shorter "
        "outdoor windows when it is cold, very hot, rainy, or stormy. (2) Put flexible outdoor items in the morning if "
        "the forecast is clearer, or add explicit \"weather backup\" ideas in the item description. (3) Fill "
        "weather_advisory with a short honest summary, what you changed, and if appropriate suggest "
        "rescheduling a different week/month. severity must be one of: ok, caution, consider_rescheduling. "
    )
    return (
        "Build a day-by-day travel itinerary. "
        "Output a single JSON object (no markdown) with these keys: "
        '"days" and "weather_advisory". '
        f"{(w_extra if weather_context else '')}"
        "Format: { \"weather_advisory\": { "
        '"summary": string (one or two sentences on how weather affects the plan), '
        '"adjustments": string (how the itinerary was adapted), '
        '"reschedule_suggestion": string or null (if not null, a concrete rescheduling hint), '
        '"severity": "ok"|"caution"|"consider_rescheduling" }, '
        '"days": [ { "day_number": 1, "day_title": string (optional), "day_summary": string, "items": [ { '
        '"item_type": "hotel|restaurant|attraction|transport", "title": str, "description": str, '
        '"start_time": string optional, "end_time": string optional, "sequence_number": int, '
        '"estimated_cost_pkr": int } ] } ] }'
        "Use estimated_cost_pkr as rough PKR. If no weather data: set weather_advisory.severity to ok and brief text."
    )


def build_itinerary_with_groq(
    destination_name,
    region,
    duration_days,
    budget_pkr,
    style_hint,
    places_context,
    weather_context="",
    weather_snapshot=None,
):
    """
    Returns { itinerary: [...], weather_advisory: dict }.
    Items are generic (no place_id). See module docstring flow (2).
    """
    n_days = int(duration_days or 3)
    if not GROQ_API_KEY:
        return _itinerary_result(
            _simple_rule_itinerary(
                destination_name, n_days, weather_context, weather_snapshot
            ),
            _normalize_weather_advisory(None, weather_snapshot),
        )

    wx = ""
    if (weather_context or "").strip():
        wx = f"\nCURRENT WEATHER (at destination coordinates, now):\n{weather_context.strip()}\n"
    user_msg = (
        f"Destination: {destination_name}, region: {region or 'Pakistan'}, "
        f"duration_days: {duration_days}, budget_PKR: {budget_pkr or 'not given'}, style: {style_hint or 'general'}. "
        f"{wx}Optional place ideas: {places_context[:2000]}"
    )
    try:
        r = _groq_post_chat(
            [
                {"role": "system", "content": _system_destination_only(weather_context)},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            json_object=True,
        )
        r.raise_for_status()
        obj = _parse_json_object_from_text(_groq_json_content(r))
        wa = _normalize_weather_advisory(obj.get("weather_advisory"), weather_snapshot)
        days = _days_from_groq_obj(obj, with_place_id=False)
        if days:
            return _itinerary_result(days, wa)
    except Exception as e:  # noqa: BLE001
        _log.warning("Groq itinerary error: %s", e)
    # Groq failed or returned empty days: deterministic placeholder days
    return _itinerary_result(
        _simple_rule_itinerary(destination_name, n_days, weather_context, weather_snapshot),
        _normalize_weather_advisory(None, weather_snapshot),
    )


# ---------------------------------------------------------------------------
# Itinerary from DB places — build_itinerary_from_places_with_groq  (flow 3)
# ---------------------------------------------------------------------------

def _catalog_json(places_list):
    """Compact JSON the model must cite by id; caps at 80 rows to save tokens."""
    catalog = []
    for p in places_list[:80]:
        la = lo = None
        try:
            if p.get("latitude") is not None:
                la = round(float(p["latitude"]), 5)
            if p.get("longitude") is not None:
                lo = round(float(p["longitude"]), 5)
        except (TypeError, ValueError):
            pass
        catalog.append(
            {
                "id": p.get("id"),
                "name": p.get("name") or "",
                "type": p.get("main_type") or "attraction",
                "cost_pkr": int(p.get("cost_pkr") or 0),
                "lat": la,
                "lon": lo,
                "address": (p.get("address") or "")[:120],
            }
        )
    return json.dumps(catalog, ensure_ascii=False)


def _system_places(weather_context):
    """Stricter system prompt: only POIs from CATALOG, with place_id rules."""
    wx_rules = (
        "When CURRENT WEATHER is provided: prefer indoor/covered catalog places (restaurants, hotels, indoor "
        "attractions) over long outdoor-only sites in bad weather; mention backup plans in descriptions. "
        'Output must include "weather_advisory" next to "days" (same shape as in the general planner). '
    )
    return (
        "You are a travel planner. Build a day-by-day itinerary using ONLY places from CATALOG (real POIs with costs). "
        "Each CATALOG item: id, name, type (hotel, restaurant, attraction), cost_pkr, lat, lon, address.\n"
        f"{(wx_rules if (weather_context or '').strip() else '')}"
        "Output a single JSON object with keys \"weather_advisory\" and \"days\". "
        "weather_advisory: { summary, adjustments, reschedule_suggestion (or null), severity: ok|caution|consider_rescheduling }. "
        "\"days\": [ {\n"
        "  \"day_number\": 1,\n"
        "  \"day_title\": string,\n"
        "  \"day_summary\": string,\n"
        "  \"items\": [ {\n"
        "    \"place_id\": <id from CATALOG> or null for transport-only rows,\n"
        "    \"item_type\": \"hotel|restaurant|attraction|transport\",\n"
        "    \"title\": string,\n"
        "    \"description\": string,\n"
        "    \"start_time\": string optional, \"end_time\": string optional,\n"
        "    \"sequence_number\": int,\n"
        "    \"estimated_cost_pkr\": int\n"
        "  } ]\n} ]\n"
        "Rules: (1) Every non-null place_id MUST exist in CATALOG. (2) Match item_type to CATALOG type. "
        "(3) At most one transport item per day with place_id null (local travel 500–3000 PKR). "
        "(4) For CATALOG places, estimated_cost_pkr should use that row's cost_pkr. "
        "(5) If total trip budget PKR is given, do not exceed it across all days. "
        "(6) Obey USER_MESSAGE. "
        "(7) Be concrete in descriptions. "
        "(8) For a D-day trip, note D-1 hotel nights in day 1 summary when D>1."
    )


def _validate_itinerary_place_ids(days_list, places_list):
    """
    After Groq returns place_ids, align each row with our DB: valid id, cost, coords, address.
    Bad or unknown ids are cleared so the trip saver does not break FKs.
    """
    by_id = {p["id"]: p for p in places_list}
    out_days = []
    for d in days_list or []:
        items_out = []
        for it in d.get("items") or []:
            it = dict(it) if it else {}
            raw_pid = it.get("place_id")
            pid_int = None
            if raw_pid is not None:
                try:
                    pid_int = int(raw_pid)
                except (TypeError, ValueError):
                    pid_int = None
            if pid_int is not None and pid_int not in by_id:
                pid_int = None
            it["place_id"] = pid_int
            it["item_type"] = _item_type(it.get("item_type"))
            if pid_int is not None:
                p = by_id[pid_int]
                it["title"] = (it.get("title") or p.get("name") or "Place")[:200]
                c = p.get("cost_pkr")
                if c is not None and int(c) > 0:
                    it["estimated_cost_pkr"] = int(it.get("estimated_cost_pkr") or c)
                try:
                    if p.get("latitude") is not None:
                        it["latitude"] = float(p["latitude"])
                    if p.get("longitude") is not None:
                        it["longitude"] = float(p["longitude"])
                except (TypeError, ValueError):
                    pass
                addr = (p.get("address") or "").strip()
                if addr:
                    it["place_address"] = addr[:500]
            it["estimated_cost_pkr"] = int(it.get("estimated_cost_pkr") or 0)
            it["sequence_number"] = int(it.get("sequence_number") or len(items_out) + 1)
            it["start_time"] = _hhmm(it.get("start_time"))
            it["end_time"] = _hhmm(it.get("end_time"))
            if it.get("description"):
                it["description"] = str(it["description"])[:2000]
            items_out.append(it)
        day_title = (d.get("day_title") or d.get("title") or "").strip()[:200] or None
        day_summary = (
            (d.get("day_summary") or d.get("day_focus") or d.get("notes") or "").strip()[:1500] or None
        )
        out_days.append(
            {
                "day_number": int(d.get("day_number") or len(out_days) + 1),
                "day_title": day_title,
                "day_summary": day_summary,
                "items": items_out,
            }
        )
    return out_days


def build_itinerary_from_places_with_groq(
    user_message,
    destination_name,
    region,
    duration_days,
    budget_pkr,
    style_hint,
    places_list,
    weather_context="",
    weather_snapshot=None,
):
    """
    Same return shape as build_itinerary_with_groq, but items may include place_id from CATALOG.
    If API key missing or no places, reuses the simpler planner. See module flow (3).
    """
    if not GROQ_API_KEY or not places_list:
        return build_itinerary_with_groq(
            destination_name,
            region,
            duration_days,
            budget_pkr,
            style_hint,
            str(places_list)[:2000],
            weather_context=weather_context,
            weather_snapshot=weather_snapshot,
        )

    cj = _catalog_json(places_list)
    wx = ""
    if (weather_context or "").strip():
        wx = f"\nCURRENT WEATHER:\n{weather_context.strip()}\n"
    user_msg = (
        f"Destination: {destination_name}, region: {region or 'Pakistan'}.\n"
        f"Duration: {int(duration_days)} day(s). "
        f"Total budget (PKR): {budget_pkr if budget_pkr is not None else 'not set'}. "
        f"Style: {style_hint or 'general'}.\n"
        f"{wx}USER_MESSAGE: {user_message or 'None — balanced plan with hotel, food, and sights.'}\n"
        f"CATALOG:\n{cj}"
    )
    try:
        r = _groq_post_chat(
            [
                {"role": "system", "content": _system_places(weather_context)},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.25,
            json_object=True,
            timeout=90,
        )
        r.raise_for_status()
        obj = _parse_json_object_from_text(_groq_json_content(r))
        wa = _normalize_weather_advisory(obj.get("weather_advisory"), weather_snapshot)
        days = _days_from_groq_obj(obj, with_place_id=True)
        if days:
            return _itinerary_result(_validate_itinerary_place_ids(days, places_list), wa)
    except Exception as e:  # noqa: BLE001
        _log.warning("Groq place-based itinerary error: %s", e)
    # Fall back: simpler itinerary with a snippet of the catalog in the user message
    return build_itinerary_with_groq(
        destination_name,
        region,
        duration_days,
        budget_pkr,
        style_hint,
        cj[:2000],
        weather_context=weather_context,
        weather_snapshot=weather_snapshot,
    )


def sum_itinerary_cost_pkr(day_plans):
    """Sums estimated_cost_pkr on every item (used to compare to trip budget)."""
    total = 0
    for d in day_plans or []:
        for it in d.get("items") or []:
            total += int(it.get("estimated_cost_pkr") or 0)
    return int(total)


def _simple_rule_itinerary(name, days, weather_context="", weather_snapshot=None):
    """
    No-AI path: 2 items per day for up to 14 days. First day text may mention bad weather
    if weather_context / snapshot suggest caution.
    """
    result = []
    sev = weather_planning_severity(weather_snapshot) if weather_snapshot else "ok"
    low = (weather_context or "").lower()
    first_day_weather = ""
    if "rain" in low or "drizzle" in low or "storm" in low or "snow" in low:
        first_day_weather = " (Weather: prefer indoor or covered options today; check forecast before long outdoor walks.)"
    elif sev in ("caution", "consider_rescheduling"):
        first_day_weather = " (Weather: see advisory — mix indoor and short outdoor time.)"
    for d in range(1, max(1, min(days, 14)) + 1):
        d1 = f"Rest and local orientation.{first_day_weather if d == 1 else ''}"
        drest = "Main sightseeing and activities."
        items = [
            {
                "item_type": "attraction" if d > 1 else "hotel",
                "title": f"Day {d}: explore {name}" if d > 1 else f"Arrival in {name}",
                "description": d1 if d == 1 else drest,
                "sequence_number": 1,
                "estimated_cost_pkr": 2000 * d,
            },
            {
                "item_type": "restaurant",
                "title": "Local food",
                "description": "Try regional food.",
                "sequence_number": 2,
                "estimated_cost_pkr": 1500,
            },
        ]
        result.append({"day_number": d, "items": items})
    return result
