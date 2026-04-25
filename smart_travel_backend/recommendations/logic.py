"""
Recommendations: give each destination a score from the user profile (no machine learning).

We use simple rules: budget, star rating, travel "style" words, and saved category list.
Used on the home page ("Picked for you") and the /api/recommendations/ route.
"""


def _style_match(profile_style, dest_category, dest_description):
    """
    Add points when the user's style text looks like the destination text
    (for example "nature" in both). We also use a small synonym table.
    """
    if not profile_style:
        return 0.0
    ps = (profile_style or "").lower()
    cat = (dest_category or "").lower()
    desc = (dest_description or "").lower()
    if ps in cat or ps in desc:
        return 1.5
    synonyms = {
        "adventure": ["adventure", "hiking", "ski", "mountain"],
        "relaxation": ["relax", "beach", "resort", "spa"],
        "nature": ["nature", "forest", "lake", "valley"],
        "culture": ["culture", "historical", "fort", "museum"],
        "family": ["family", "weekend", "hill"],
        "luxury": ["luxury", "premium"],
    }
    for key, words in synonyms.items():
        if key in ps:
            for w in words:
                if w in cat or w in desc:
                    return 1.2
    return 0.2


def score_destinations_for_user(destinations, profile, max_budget_hint=None):
    """
    For each place, compute one number. Higher = better for this user.

    `profile` may have:
    - `budget_range`: economy / standard / premium (we turn it into a PKR cap)
    - `preferred_travel_style`: one short word
    - `preferred_categories`: comma list from the profile checkboxes
    - `typical_trip_duration_days` (we do not use it much here today)

    `max_budget_hint` can set the PKR cap directly (if we already know it from the request).
    """
    budget_map = {"economy": 20000, "standard": 40000, "premium": 100000}
    user_cap = max_budget_hint
    if user_cap is None and profile and profile.get("budget_range"):
        br = (profile.get("budget_range") or "standard").lower()
        user_cap = budget_map.get(br) or 40000

    scores = []
    for d in destinations:
        score = 0.0
        reason_parts = []  # short text for UI / debug

        cost = int(d.get("cost") or d.get("priceFrom") or 0)
        rating = float(d.get("user_rating") or d.get("rating") or 0)

        if user_cap and cost > 0 and cost <= user_cap:
            score += 1.0
            reason_parts.append("fits budget")
        elif user_cap and cost > user_cap:
            score += max(0, 0.5 - (cost - user_cap) / max(1, user_cap))
        else:
            score += 0.3

        score += (rating / 5.0) * 1.2
        reason_parts.append("rating")

        pstyle = (
            (profile or {}).get("preferred_travel_style")
            or (profile or {}).get("selected_styles")
        )
        if isinstance(pstyle, str) and pstyle:
            m = _style_match(pstyle, d.get("category") or d.get("type"), d.get("description"))
            score += m
            if m > 0.5:
                reason_parts.append("style match")

        # Categories from the profile (must match the destination "category" field text)
        cats = (profile or {}).get("preferred_categories") or ""
        if isinstance(cats, str) and cats:
            dcat = (d.get("category") or "").lower()
            d_tokens = {t.strip() for t in dcat.replace(",", " ").split() if t.strip()}
            for part in cats.split(","):
                part = part.strip().lower()
                if not part:
                    continue
                if part in dcat or part in d_tokens:
                    score += 0.8
                    reason_parts.append("category interest")

        scores.append(
            {
                "destination": d,
                "score": round(float(score) + 0.0001, 4),
                "reason": ", ".join(reason_parts[:3]) or "popular pick",
            }
        )

    scores.sort(key=lambda x: -x["score"])
    return scores


def run_recommendation(user_id, profile, all_destinations, top_n=8):
    """
    Same as score_destinations_for_user, but we only return the first `top_n` rows
    and add a label `algorithm` for the front end. `user_id` is for logging / future use.
    """
    ranked = score_destinations_for_user(all_destinations, profile)
    out = []
    for r in ranked[:top_n]:
        out.append(
            {
                "destination": r["destination"],
                "score": r["score"],
                "reason": r["reason"],
                "algorithm": "content_based",
            }
        )
    return out
