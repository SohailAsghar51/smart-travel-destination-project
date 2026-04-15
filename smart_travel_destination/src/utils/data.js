import staticDest from '../data/destinations_full.json';

// Return destinations persisted by admin in localStorage if present, otherwise return bundled JSON
export function getAllDestinations() {
  try {
    const raw = localStorage.getItem('admin_destinations');
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (e) {
    // ignore parse errors and fall back
  }
  return staticDest;
}

// Save updated destinations to localStorage (admin feature)
export function saveAllDestinations(list) {
  localStorage.setItem('admin_destinations', JSON.stringify(list));
}

export default { getAllDestinations, saveAllDestinations };
