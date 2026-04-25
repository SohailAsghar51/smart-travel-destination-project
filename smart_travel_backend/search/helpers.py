"""
Search helper: pick the best destinations from a list the database already filtered
(for example same region and budget).

The user types a sentence. The AI (Groq) may return a place name or only a theme
(like "mountains"). We never throw away the budget filter — we only sort and cut
the list that the database gave us.
"""

import re

# Words that mean "mountains" but are NOT a city name (we use this to choose keyword sets)
MOUNTAIN_ALIASES = frozenset(
    {
        "mountains",
        "mountain",
        "hills",
        "hill",
        "highlands",
    }
)
# Same idea for beach-style trips
BEACH_ALIASES = frozenset({"beach", "beaches", "coast", "coastal", "seaside"})

# If the query is about mountains, we add points when these words appear in name/region/text
MOUNTAIN_KEYWORDS = {
    "mountain",
    "hill",
    "valley",
    "nature",
    "scenic",
    "alpine",
    "hiking",
    "kpk",
    "khyber",
    "gilgit",
    "baltistan",
    "gb",
    "northern",
    "hunza",
    "naran",
    "kaghan",
    "skardu",
    "murree",
    "nathia",
    "galyat",
    "chitral",
    "swat",
    "ayubia",
    "shogran",
    "fairy",
    "kumrat",
    "ajk",
    "kashmir",
    "pir sohawa",
    "rawalakot",
    "ziarat",
    "kund",
    "fairy meadows",
}
# Words that help a "beach" style search
BEACH_KEYWORDS = {
    "beach",
    "coast",
    "coastal",
    "seaside",
    "sea",
}

# Small words we ignore when we read the user sentence (not useful for matching)
STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "in",
        "for",
        "with",
        "under",
        "over",
        "plan",
        "trip",
        "trav",
        "days",
        "day",
        "pkr",
        "rs",
        "rupee",
        "rupees",
    }
)


def _blob(d):
    """One long lowercase string from a destination row (easy to search inside)."""
    return " ".join(
        [
            str(d.get("name") or ""),
            str(d.get("region") or ""),
            str(d.get("category") or ""),
            str(d.get("description") or ""),
        ]
    ).lower()


def _score_for_theme(blob, kws, rating):
    """Higher score = more words from `kws` found in `blob`. We also add a little from `rating`."""
    s = 0.0
    for kw in kws:
        if len(kw) > 1 and kw in blob:
            s += 1.0 if len(kw) > 4 else 0.6
    s += 0.12 * float(rating or 0)
    return s


def _mountain_mismatch_penalty(d, blob, is_mountain_theme):
    """
    If the user asked for mountains, we lower the score of pure city / beach lines
    (simple rule, not perfect).
    """
    if not is_mountain_theme:
        return 0.0
    cat = (d.get("category") or "").lower()
    s = 0.0
    if "beach" in cat and "mountain" not in blob and "hill" not in blob:
        s -= 1.2
    if any(x in blob for x in ("mosque", "masjid", "badshahi", "data darbar")):
        s -= 0.9
    return s


def select_destinations_for_search(
    candidates,
    extracted,
    raw_query,
    limit=24,
):
    """
    Main function used by the /api/search/ route.

    - `candidates`: list of places from the DB (already limited by region / budget if we did that in SQL)
    - `extracted`: small dict from the NLP step (place name, style, money, days, …)
    - `raw_query`: the original user text (lowercased inside this function for matching)
    - `limit`: how many results we return at the end
    """
    if not candidates:
        return []
    ex = extracted or {}
    qlow = (raw_query or "").lower()
    name_hint = (ex.get("destination") or "").strip()
    dlow = name_hint.lower() if name_hint else ""

    # Step A: user gave a real place or region name → keep rows whose name/region contains that string
    if dlow and dlow not in MOUNTAIN_ALIASES and dlow not in BEACH_ALIASES:
        sub = [
            d
            for d in candidates
            if dlow in (d.get("name") or "").lower() or dlow in (d.get("region") or "").lower()
        ]
        if sub:
            sub.sort(key=lambda d: -float(d.get("rating", 0) or 0))
            return sub[:limit]

    # Step B: theme or generic search → build a set of "active" keywords, then score each row
    active_kws = set()
    is_mountain = dlow in MOUNTAIN_ALIASES or "mountain" in qlow or "mountains" in qlow or "hiking" in qlow
    is_beach = dlow in BEACH_ALIASES or "beach" in qlow

    if is_mountain and not is_beach:
        active_kws |= MOUNTAIN_KEYWORDS
    if is_beach and not is_mountain:
        active_kws |= BEACH_KEYWORDS
    if is_mountain and is_beach:
        active_kws |= MOUNTAIN_KEYWORDS | {"beach"}

    # Pull longer words (3+ letters) from the user text into the keyword set
    for w in re.findall(r"[a-z]{3,}", qlow):
        if w not in STOP and w not in ("plan", "trip", "kpk", "kpkk"):
            active_kws.add(w)
    for w in re.findall(r"[a-z]{3,}", dlow):
        if w not in STOP and w not in MOUNTAIN_ALIASES and w not in BEACH_ALIASES:
            active_kws.add(w)

    st = (ex.get("travel_style") or "").lower()
    if st in ("adventure", "nature"):
        active_kws |= {"nature", "mountain", "hill", "valley", "scenic"}
    if st == "relaxation" and is_beach:
        active_kws |= BEACH_KEYWORDS

    if not active_kws:
        active_kws = {w for w in re.findall(r"[a-z]{3,}", qlow) if w not in STOP}

    def total_score(d):
        blob = _blob(d)
        r = float(d.get("rating", 0) or 0)
        sc = _score_for_theme(blob, active_kws, r)
        if is_mountain and not is_beach:
            sc += _mountain_mismatch_penalty(d, blob, True)
        return sc

    ranked = sorted(candidates, key=lambda d: -total_score(d))
    if total_score(ranked[0]) <= 0 and len(candidates) > 0:
        # No keyword really matched: still return from the same pool, sort by star rating
        ranked = sorted(
            candidates, key=lambda d: -float(d.get("rating", 0) or 0)
        )
    return ranked[:limit]
