import os
from pathlib import Path

# Load .env from this package directory (so it works no matter the shell cwd)
_env = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv

    load_dotenv(_env)
    load_dotenv()  # also cwd .env if present
except ImportError:
    pass

# MySQL
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Pass456")
DB_NAME = os.environ.get("DB_NAME", "ai_travel_buddy")

# Groq (OpenAI-compatible API) — do not commit real keys; set GROQ_API_KEY in .env
GROQ_API_KEY = (os.environ.get("GROQ_API_KEY") or "").strip()
# Default: widely available on Groq; override with GROQ_MODEL in .env if you prefer
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Optional: RapidAPI — Open Weather 13 (lat/lon; register at rapidapi.com, subscribe to the API)
# Do not commit real keys. Example: RAPIDAPI_KEY=... and optional RAPIDAPI_WEATHER_HOST
RAPIDAPI_KEY = (os.environ.get("RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY_WEATHER") or "").strip()
RAPIDAPI_WEATHER_HOST = os.environ.get("RAPIDAPI_WEATHER_HOST", "open-weather13.p.rapidapi.com")
RAPIDAPI_WEATHER_URL = os.environ.get(
    "RAPIDAPI_WEATHER_URL",
    "https://open-weather13.p.rapidapi.com/latlon",
)

