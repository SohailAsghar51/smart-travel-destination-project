import rates from '../data/average_rates.json';

// Estimate total cost for a trip to a destination given duration (days)
export function estimateTripCost(dest, duration = 3) {
  // hotel cost = hotelPerNight * nights (nights = days)
  const hotel = (rates.hotelPerNight || 0) * duration;

  // food cost = foodPerDay * days
  const food = (rates.foodPerDay || 0) * duration;

  // travel estimate: use destination.cost as indicative (if present) or default to averageTravel
  const travelBase = dest.cost || rates.averageTravel || 0;
  // if dest.cost likely a per-trip package, use a fraction; otherwise use averageTravel
  const travel = travelBase * 0.6 + (rates.averageTravel || 0) * 0.4;

  const subtotal = hotel + food + travel;
  const tax = (rates.taxPercent || 0) / 100 * subtotal;
  const total = Math.round(subtotal + tax);

  return {
    hotel: Math.round(hotel),
    food: Math.round(food),
    travel: Math.round(travel),
    tax: Math.round(tax),
    total
  };
}

export default { estimateTripCost };
