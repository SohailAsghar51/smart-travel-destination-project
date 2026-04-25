import json
import logging
import re

import requests

from config import GROQ_API_KEY, GROQ_MODEL
from weather_rapidapi import weather_planning_severity

_log = logging.getLogger(__name__)


def _hhmm(s):
    """Normalize a time string to HH:MM for API JSON, or None."""
    if s is None or s == "":
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _itinerary_result(itin, weather_advisory=None):
    return {"itinerary": itin, "weather_advisory": weather_advisory}


def _normalize_weather_advisory(raw, weather_snapshot=None):
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


def _groq_post_chat(messages, temperature, json_object, timeout=60):
    body = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_object:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
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


def _parse_json_object_from_text(content):
    """
    Model output may include markdown fences, or a short preamble before the JSON.
    """
    s = (content or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i = s.find("{")
        j = s.rfind("}")
        if i != -1 and j > i:
            return json.loads(s[i : j + 1])
        raise


def parse_travel_nlp(text, user_id=None):
    """
    Returns (extracted_dict, nlp_source, error_or_none)
    nlp_source is one of: "groq", "unconfigured", "fallback"
    """
    if not GROQ_API_KEY:
        parsed = _fallback_parse(text)
        return _normalize_nlp_from_fallback(parsed, text), "unconfigured", "GROQ_API_KEY is not set in environment or .env (see smart_travel_backend/.env)"

    system = (
        "You extract travel planning parameters from the user's message. "
        "Output a single JSON object only (no markdown, no text before or after). "
        "Keys: intent (one of: travel_planning, search, budget_check), "
        "destination (string or null), duration_days (integer or null), budget_pkr (integer or null), "
        "travel_style (one of: adventure, relaxation, culture, family, nature, luxury, or null), "
        "region (string or null), activity_hint (string or null). "
        "All numbers must be plain integers, not strings."
    )
    err_note = None
    try:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text or ""},
        ]
        r = _groq_post_chat(messages, temperature=0.1, json_object=True)
        if not r.ok:
            err_body = (r.text or "")[:500]
            err_note = f"HTTP {r.status_code}: {err_body}"
            _log.warning("Groq NLP HTTP error: %s", err_note)
            parsed = _fallback_parse(text)
            return _normalize_nlp_from_fallback(parsed, text), "fallback", err_note

        data = r.json()
        content = data["choices"][0]["message"]["content"]
        try:
            obj = _parse_json_object_from_text(content)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            err_note = f"JSON parse: {e}"
            _log.warning("Groq NLP JSON error: %s; content=%.200r", err_note, content)
            parsed = _fallback_parse(text)
            return _normalize_nlp_from_fallback(parsed, text), "fallback", err_note

        return _normalize_nlp_result(obj, text), "groq", None
    except requests.RequestException as e:
        err_note = str(e)[:500]
        _log.warning("Groq NLP request error: %s", err_note)
    except (KeyError, IndexError) as e:
        err_note = f"Response shape: {e}"
        _log.warning("Groq NLP response error: %s", err_note)
    except Exception as e:  # noqa: BLE001 — log and fall back
        err_note = str(e)[:500]
        _log.warning("Groq NLP error: %s", err_note)

    parsed = _fallback_parse(text)
    return _normalize_nlp_from_fallback(parsed, text), "fallback", err_note


def _normalize_nlp_from_fallback(fallback_dict, text):
    """Merge rule-based result with a minimal pass through the same normalizer as Groq (dict shape)."""
    return _normalize_nlp_result(fallback_dict, text)


def parse_travel_query_with_groq(text, user_id=None):
    """Backward-compatible: only the extracted parameters dict."""
    d, _src, _err = parse_travel_nlp(text, user_id)
    return d


def _normalize_nlp_result(obj, original_text):
    if not isinstance(obj, dict):
        return _normalize_nlp_result({}, original_text)
    out = {
        "intent": obj.get("intent") or "travel_planning",
        "destination": obj.get("destination"),
        "duration_days": obj.get("duration_days"),
        "budget_pkr": obj.get("budget_pkr"),
        "travel_style": obj.get("travel_style"),
        "region": obj.get("region"),
        "activity_hint": obj.get("activity_hint"),
    }
    if out["duration_days"] is not None:
        try:
            out["duration_days"] = int(out["duration_days"])
        except (TypeError, ValueError):
            out["duration_days"] = None
    if out["budget_pkr"] is not None:
        try:
            out["budget_pkr"] = int(out["budget_pkr"])
        except (TypeError, ValueError):
            out["budget_pkr"] = None
    return out


def _fallback_parse(text):
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
    If CURRENT_WEATHER is present, the model should adjust outdoor blocks and fill weather_advisory.
    """
    n_days = int(duration_days or 3)
    if not GROQ_API_KEY:
        return _itinerary_result(
            _simple_rule_itinerary(
                destination_name, n_days, weather_context, weather_snapshot
            ),
            _normalize_weather_advisory(None, weather_snapshot),
        )

    w_extra = (
        "When CURRENT WEATHER is provided, you MUST: (1) Prefer indoor or covered activities, museums, and shorter "
        "outdoor windows when it is cold, very hot, rainy, or stormy. (2) Put flexible outdoor items in the morning if "
        "the forecast is clearer, or add explicit \"weather backup\" ideas in the item description. (3) Fill "
        "weather_advisory with a short honest summary, what you changed, and if appropriate suggest "
        "rescheduling a different week/month. severity must be one of: ok, caution, consider_rescheduling. "
    )
    system = (
        "Build a day-by-day travel itinerary. "
        "Output a single JSON object (no markdown) with these keys: "
        "\"days\" and \"weather_advisory\". "
        f"{w_extra if weather_context else ''}"
        "Format: { \"weather_advisory\": { "
        "\"summary\": string (one or two sentences on how weather affects the plan), "
        "\"adjustments\": string (how the itinerary was adapted), "
        "\"reschedule_suggestion\": string or null (if not null, a concrete rescheduling hint), "
        "\"severity\": \"ok\"|\"caution\"|\"consider_rescheduling\" }, "
        "\"days\": [ { "
        "\"day_number\": 1, "
        "\"day_title\": string (optional), "
        "\"day_summary\": string, "
        "\"items\": [ { "
        "\"item_type\": \"hotel|restaurant|attraction|transport\", "
        "\"title\": str, "
        "\"description\": str, "
        "\"start_time\": string optional, \"end_time\": string optional, "
        "\"sequence_number\": int, "
        "\"estimated_cost_pkr\": int } ] } ] } "
        "Use estimated_cost_pkr as rough PKR. If no weather data: set weather_advisory.severity to ok and brief text."
    )
    wx = ""
    if (weather_context or "").strip():
        wx = f"\nCURRENT WEATHER (at destination coordinates, now):\n{weather_context.strip()}\n"
    user_msg = (
        f"Destination: {destination_name}, region: {region or 'Pakistan'}, "
        f"duration_days: {duration_days}, budget_PKR: {budget_pkr or 'not given'}, style: {style_hint or 'general'}. "
        f"{wx}"
        f"Optional place ideas: {places_context[:2000]}"
    )
    try:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
        r = _groq_post_chat(messages, temperature=0.4, json_object=True)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        obj = _parse_json_object_from_text(content)
        wa = _normalize_weather_advisory(obj.get("weather_advisory"), weather_snapshot)
        days = obj.get("days") or []
        result = []
        for d in days:
            items = d.get("items") or []
            clean_items = []
            for i, it in enumerate(items):
                it = it or {}
                raw_type = (it.get("item_type") or "attraction").lower()
                if raw_type not in ("hotel", "restaurant", "attraction", "transport"):
                    raw_type = "attraction"
                clean_items.append(
                    {
                        "item_type": raw_type,
                        "title": (it.get("title") or "Visit")[:200],
                        "description": (it.get("description") or "")[:2000],
                        "start_time": _hhmm(it.get("start_time")),
                        "end_time": _hhmm(it.get("end_time")),
                        "sequence_number": int(it.get("sequence_number") or (i + 1)),
                        "estimated_cost_pkr": int(it.get("estimated_cost_pkr") or 0),
                    }
                )
            result.append(
                {
                    "day_number": int(d.get("day_number") or len(result) + 1),
                    "day_title": (d.get("day_title") or d.get("title") or "")[:200] or None,
                    "day_summary": (d.get("day_summary") or d.get("day_focus") or d.get("notes") or "")[:1500] or None,
                    "items": clean_items,
                }
            )
        if result:
            return _itinerary_result(result, wa)
    except Exception as e:  # noqa: BLE001
        _log.warning("Groq itinerary error: %s", e)
    return _itinerary_result(
        _simple_rule_itinerary(destination_name, n_days, weather_context, weather_snapshot),
        _normalize_weather_advisory(None, weather_snapshot),
    )


def _validate_itinerary_place_ids(days_list, places_list):
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
            itype = (it.get("item_type") or "attraction").lower()
            if itype not in ("hotel", "restaurant", "attraction", "transport"):
                itype = "attraction"
            it["item_type"] = itype
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
    Plans using ONLY rows from `places`. Returns { itinerary, weather_advisory }.
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
    # Compact catalog for the model (keep token size reasonable)
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
                "address": ((p.get("address") or "")[:120]),
            }
        )
    catalog_json = json.dumps(catalog, ensure_ascii=False)
    wx_rules = (
        "When CURRENT WEATHER is provided: prefer indoor/covered catalog places (restaurants, hotels, indoor "
        "attractions) over long outdoor-only sites in bad weather; mention backup plans in descriptions. "
        "Output must include \"weather_advisory\" next to \"days\" (same shape as in the general planner). "
    )
    system = (
        "You are a travel planner. Build a day-by-day itinerary using ONLY places from CATALOG (real POIs with costs). "
        "Each CATALOG item: id, name, type (hotel, restaurant, attraction), cost_pkr, lat, lon, address.\n"
        f"{wx_rules if (weather_context or '').strip() else ''}"
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
    wx = ""
    if (weather_context or "").strip():
        wx = f"\nCURRENT WEATHER:\n{weather_context.strip()}\n"
    user_msg = (
        f"Destination: {destination_name}, region: {region or 'Pakistan'}.\n"
        f"Duration: {int(duration_days)} day(s). "
        f"Total budget (PKR): {budget_pkr if budget_pkr is not None else 'not set'}. "
        f"Style: {style_hint or 'general'}.\n"
        f"{wx}"
        f"USER_MESSAGE: {user_message or 'None — balanced plan with hotel, food, and sights.'}\n"
        f"CATALOG:\n{catalog_json}"
    )
    try:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
        r = _groq_post_chat(messages, temperature=0.25, json_object=True, timeout=90)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        obj = _parse_json_object_from_text(content)
        wa = _normalize_weather_advisory(obj.get("weather_advisory"), weather_snapshot)
        days = obj.get("days") or []
        result = []
        for d in days:
            clean_items = []
            for i, it in enumerate(d.get("items") or []):
                it = it or {}
                raw_type = (it.get("item_type") or "attraction").lower()
                if raw_type not in ("hotel", "restaurant", "attraction", "transport"):
                    raw_type = "attraction"
                clean_items.append(
                    {
                        "place_id": it.get("place_id"),
                        "item_type": raw_type,
                        "title": (it.get("title") or "Activity")[:200],
                        "description": (it.get("description") or "")[:2000],
                        "start_time": _hhmm(it.get("start_time")),
                        "end_time": _hhmm(it.get("end_time")),
                        "sequence_number": int(it.get("sequence_number") or (i + 1)),
                        "estimated_cost_pkr": int(it.get("estimated_cost_pkr") or 0),
                    }
                )
            result.append(
                {
                    "day_number": int(d.get("day_number") or len(result) + 1),
                    "day_title": (d.get("day_title") or d.get("title") or "")[:200] or None,
                    "day_summary": (d.get("day_summary") or d.get("day_focus") or d.get("notes") or "")[:1500] or None,
                    "items": clean_items,
                }
            )
        if result:
            return _itinerary_result(
                _validate_itinerary_place_ids(result, places_list),
                wa,
            )
    except Exception as e:  # noqa: BLE001
        _log.warning("Groq place-based itinerary error: %s", e)
    return build_itinerary_with_groq(
        destination_name,
        region,
        duration_days,
        budget_pkr,
        style_hint,
        catalog_json[:2000],
        weather_context=weather_context,
        weather_snapshot=weather_snapshot,
    )


def sum_itinerary_cost_pkr(day_plans):
    total = 0
    for d in day_plans or []:
        for it in d.get("items") or []:
            total += int(it.get("estimated_cost_pkr") or 0)
    return int(total)


def _simple_rule_itinerary(name, days, weather_context="", weather_snapshot=None):
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
