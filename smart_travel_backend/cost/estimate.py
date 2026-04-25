"""
Very simple trip cost estimate in PKR (not from real hotel prices — for UI only).

The idea matches the small JavaScript file on the front (utils/cost.js) so the user
sees a similar number in the browser and in the API if we use this function.
"""

# Fixed "per night / per day" style numbers. Change them if you want other defaults.
RATES = {
    "hotelPerNight": 4000,
    "foodPerDay": 2000,
    "averageTravel": 5000,
    "taxPercent": 0,  # set to 5 for 5% if you add tax
}


def estimate_trip_cost(dest, duration=3):
    """
    Return a small breakdown: hotel, food, travel, tax, total.

    `dest` = destination dict from the API (we read `cost` = average per day in PKR).
    `duration` = number of days for the whole trip.
    """
    d = RATES
    cost_base = int(dest.get("cost") or dest.get("priceFrom") or 0)
    # Rough split: we mix the destination "per day" cost with a fixed travel idea
    hotel = d["hotelPerNight"] * duration
    food = d["foodPerDay"] * duration
    travel = cost_base * 0.4 + d["averageTravel"] * 0.4
    subtotal = hotel + food + travel
    tax = (d["taxPercent"] or 0) / 100.0 * subtotal
    total = int(round(subtotal + tax))
    return {
        "hotel": int(hotel),
        "food": int(food),
        "travel": int(travel),
        "tax": int(tax),
        "total": total,
    }
