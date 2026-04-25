"""
RapidAPI Open Weather 13 — current conditions by lat/lon.
https://open-weather13.p.rapidapi.com/latlon?latitude=&longitude=&lang=EN
Response is OpenWeatherMap-style; temperatures in Kelvin by default.
"""

import logging
from typing import Any, Optional

import requests

from config import RAPIDAPI_KEY, RAPIDAPI_WEATHER_HOST, RAPIDAPI_WEATHER_URL

_log = logging.getLogger(__name__)


def _to_celsius(temp: Any) -> Optional[float]:
    if temp is None:
        return None
    try:
        v = float(temp)
    except (TypeError, ValueError):
        return None
    if v > 200:
        v = v - 273.15
    return round(v, 1)


def fetch_weather_latlon(latitude: float, longitude: float, lang: str = "EN", timeout: int = 12):
    """
    Returns a small dict for the app: location, summary, temp_c, feels_c, humidity, wind_m_s.
    None if the key is missing or the request failed.
    """
    if not RAPIDAPI_KEY:
        return None
    try:
        la = float(latitude)
        lo = float(longitude)
    except (TypeError, ValueError):
        return None
    try:
        r = requests.get(
            RAPIDAPI_WEATHER_URL,
            params={"latitude": la, "longitude": lo, "lang": lang},
            headers={
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": RAPIDAPI_WEATHER_HOST,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            _log.info("RapidAPI weather HTTP %s: %s", r.status_code, (r.text or "")[:200])
            return None
        w = r.json()
    except requests.RequestException as e:
        _log.info("RapidAPI weather request error: %s", e)
        return None
    except ValueError as e:
        _log.info("RapidAPI weather bad JSON: %s", e)
        return None

    m = w.get("main") or {}
    wlist = w.get("weather") or []
    desc = ""
    wmain = wid = None
    if wlist and isinstance(wlist[0], dict):
        w0 = wlist[0]
        desc = w0.get("description", "") or ""
        wmain = w0.get("main")
        wid = w0.get("id")
    win = w.get("wind") if isinstance(w.get("wind"), dict) else {}
    wind_ms = None
    if win.get("speed") is not None:
        try:
            wind_ms = round(float(win["speed"]), 1)
        except (TypeError, ValueError):
            pass
    return {
        "location": w.get("name", "") or "",
        "summary": str(desc).strip(),
        "weather_main": wmain,
        "weather_id": wid,
        "temp_c": _to_celsius(m.get("temp")),
        "feels_c": _to_celsius(m.get("feels_like")),
        "humidity": m.get("humidity"),
        "wind_m_s": wind_ms,
        "source": "rapidapi_open_weather13",
    }


def format_weather_context_for_groq(w: Optional[dict]) -> str:
    """
    One block of text for the trip-planning model (no API key in output).
    """
    if not w:
        return ""
    parts = [
        f"Location label: {w.get('location') or 'unknown'}.",
        f"Current conditions: {w.get('summary') or 'unknown'}.",
    ]
    if w.get("weather_main"):
        parts.append(f"Type: {w['weather_main']}.")
    if w.get("temp_c") is not None:
        parts.append(f"Temperature ~{w['temp_c']}°C")
        if w.get("feels_c") is not None:
            parts[-1] += f", feels like {w['feels_c']}°C"
        parts[-1] += "."
    if w.get("humidity") is not None:
        parts.append(f"Humidity {w['humidity']}%.")
    if w.get("wind_m_s") is not None:
        parts.append(f"Wind {w['wind_m_s']} m/s.")
    return " ".join(parts)


def weather_planning_severity(w: Optional[dict]) -> str:
    """
    Heuristic: ok | caution | consider_rescheduling
    (Used if the model omits severity; OWM condition codes. See openweathermap.org/weather-conditions)
    """
    if not w:
        return "ok"
    wid = w.get("weather_id")
    try:
        wid = int(wid) if wid is not None else None
    except (TypeError, ValueError):
        wid = None
    if wid is not None:
        if 200 <= wid < 300:
            return "consider_rescheduling"
        if 500 <= wid <= 531 or 300 <= wid <= 321:
            return "caution"
        if 600 <= wid <= 622 or 801 <= wid <= 802:
            return "caution"
    sm = (w.get("summary") or "").lower()
    if any(x in sm for x in ("thunder", "storm", "heavy rain", "extreme", "tornado", "hurricane")):
        return "consider_rescheduling"
    if any(x in sm for x in ("rain", "drizzle", "snow", "sleet", "fog", "mist", "hail")):
        return "caution"
    ws = w.get("wind_m_s")
    if ws is not None and float(ws) >= 12:
        return "caution"
    t = w.get("temp_c")
    if t is not None and (float(t) >= 40 or float(t) <= 0):
        return "caution"
    return "ok"
