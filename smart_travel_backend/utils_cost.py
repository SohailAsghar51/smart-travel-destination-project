# Rough PKR trip estimate (same idea as the React utils/cost.js)

RATES = {
    "hotelPerNight": 4000,
    "foodPerDay": 2000,
    "averageTravel": 5000,
    "taxPercent": 0,
}


def estimate_trip_cost(dest, duration=3):
    d = RATES
    cost_base = int(dest.get("cost") or dest.get("priceFrom") or 0)
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
