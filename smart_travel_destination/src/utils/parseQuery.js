// Very small heuristic parser to extract destination, days, budget from a free-text query.
export default function parseQuery(text) {
  if (!text) return {};
  const t = text.toLowerCase();

  // days: look for '3-day', '3 day', 'for 3 days'
  const daysMatch = t.match(/(\d+)\s*-?\s*day(s)?/i) || t.match(/for\s+(\d+)\s+day(s)?/i);
  const days = daysMatch ? Number(daysMatch[1]) : undefined;

  // budget: look for 'under 25000', '25,000 pk', '25000 pk', 'under 25,000 PKR'
  const budgetMatch = t.match(/under\s+([\d,]+)/i) || t.match(/(\d[\d,]+)\s*(pkr|pkrs|rs|rs\.|rupees)?/i);
  let budget;
  if (budgetMatch) {
    budget = Number(budgetMatch[1].replace(/,/g, ''));
  }

  // destination: look for 'to X' or 'in X' or 'trip to X'
  let dest;
  const toMatch = t.match(/(?:trip to|to|in)\s+([a-z\s]+)/i);
  if (toMatch) {
    // stop at common delimiters 'under', 'for', 'within', 'in', 'with'
    dest = toMatch[1].split(/\b(under|for|within|with|in|budget)\b/)[0].trim();
    // remove trailing numbers
    dest = dest.replace(/[\d,]+/g, '').trim();
  }

  return { destination: dest || undefined, days, budget };
}
