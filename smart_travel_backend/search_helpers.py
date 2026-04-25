"""
Ranks pre-filtered destination rows (same budget/region) using NLP + keyword themes.
When Groq returns a generic label like "mountains" (no place name to substring-match),
we must not fall back to an unrelated list — we score within the budget/region pool.
"""

import re

# "destination" values that are themes, not place names
MOUNTAIN_ALIASES = frozenset(
    {
        "mountains",
        "mountain",
        "hills",
        "hill",
        "highlands",
    }
)
BEACH_ALIASES = frozenset({"beach", "beaches", "coast", "coastal", "seaside"})

# Substrings to score against name|region|category|description
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
BEACH_KEYWORDS = {
    "beach",
    "coast",
    "coastal",
    "seaside",
    "sea",
}

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
    return " ".join(
        [
            str(d.get("name") or ""),
            str(d.get("region") or ""),
            str(d.get("category") or ""),
            str(d.get("description") or ""),
        ]
    ).lower()


def _score_for_theme(blob, kws, rating):
    s = 0.0
    for kw in kws:
        if len(kw) > 1 and kw in blob:
            s += 1.0 if len(kw) > 4 else 0.6
    s += 0.12 * float(rating or 0)
    return s


def _mountain_mismatch_penalty(d, blob, is_mountain_theme):
    """Down-rank city-only / beach when user asked for mountains (heuristic)."""
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
    `candidates` = rows already limited by region / max_budget (from DB).
    """
    if not candidates:
        return []
    ex = extracted or {}
    qlow = (raw_query or "").lower()
    name_hint = (ex.get("destination") or "").strip()
    dlow = name_hint.lower() if name_hint else ""

    # 1) Specific place name / region: substring match in DB fields
    if dlow and dlow not in MOUNTAIN_ALIASES and dlow not in BEACH_ALIASES:
        sub = [
            d
            for d in candidates
            if dlow in (d.get("name") or "").lower() or dlow in (d.get("region") or "").lower()
        ]
        if sub:
            sub.sort(key=lambda d: -float(d.get("rating", 0) or 0))
            return sub[:limit]

    # 2) Theme: mountains / beaches / or generic words from the query
    active_kws = set()
    is_mountain = dlow in MOUNTAIN_ALIASES or "mountain" in qlow or "mountains" in qlow or "hiking" in qlow
    is_beach = dlow in BEACH_ALIASES or "beach" in qlow

    if is_mountain and not is_beach:
        active_kws |= MOUNTAIN_KEYWORDS
    if is_beach and not is_mountain:
        active_kws |= BEACH_KEYWORDS
    if is_mountain and is_beach:
        active_kws |= MOUNTAIN_KEYWORDS | {"beach"}

    # Add meaningful tokens from the user query
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
        # no keyword hit — keep budget pool, order by rating
        ranked = sorted(
            candidates, key=lambda d: -float(d.get("rating", 0) or 0)
        )
    return ranked[:limit]
