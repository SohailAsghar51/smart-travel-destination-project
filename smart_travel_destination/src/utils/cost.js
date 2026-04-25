/**
 * Client-side cost breakdown using destination `cost` (avg per day, PKR) from the API
 * and the same defaults as `smart_travel_backend/cost/estimate.py` — no static JSON.
 */
const DEFAULT_RATES = {
  hotelPerNight: 4000,
  foodPerDay: 2000,
  averageTravel: 5000,
  taxPercent: 0,
};

// Estimate total cost for a trip to a destination given duration (days)
export function estimateTripCost(dest, duration = 3) {
  const r = DEFAULT_RATES;
  const d = dest || {};
  const costBase = Number(d.cost != null ? d.cost : d.priceFrom) || 0;
  const hotel = r.hotelPerNight * duration;
  const food = r.foodPerDay * duration;
  const travel = costBase * 0.4 + r.averageTravel * 0.4;
  const subtotal = hotel + food + travel;
  const tax = (r.taxPercent / 100) * subtotal;
  const total = Math.round(subtotal + tax);
  return {
    hotel: Math.round(hotel),
    food: Math.round(food),
    travel: Math.round(travel),
    tax: Math.round(tax),
    total,
  };
}

const costUtil = { estimateTripCost };
export default costUtil;
