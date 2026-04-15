// Simple recommendation utilities: content-based scoring and a tiny collaborative mock

function scoreContentBased(profile, dest) {
  if (!profile) return 0;
  let score = 0;

  // budget match
  if (profile.budget) {
    const diff = Math.max(0, dest.cost - profile.budget);
    score += Math.max(0, 1 - diff / Math.max(1, profile.budget));
  }

  // style / type match
  if (profile.styles && profile.styles.length) {
    const styleMatch = profile.styles.includes(dest.type) ? 1 : 0;
    score += styleMatch * 1.2;
    // tags overlap
    const tags = dest.tags || [];
    const overlap = tags.filter((t) => profile.styles.map(s => s.toLowerCase()).includes(t.toLowerCase())).length;
    score += overlap * 0.4;
  }

  // activities overlap
  if (profile.activities && profile.activities.length) {
    const overlap = dest.activities.filter((a) => profile.activities.includes(a)).length;
    score += overlap * 0.5;
  }

  // user rating and safety boost
  score += (dest.user_rating || dest.user_rating === 0 ? dest.user_rating / 5 : 0) * 0.8;
  score += (dest.safety_rating || 0) / 5 * 0.4;

  return score;
}

export function recommendContent(profile, allDestinations, top = 6) {
  const scored = allDestinations.map((d) => ({ d, score: scoreContentBased(profile, d) }));
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, top).map((s) => s.d);
}

// Collaborative mock: find other users' saved preferences or likes in localStorage
export function recommendCollaborative(profile, allDestinations, top = 6) {
  try {
    const users = JSON.parse(localStorage.getItem('st_users') || '[]');
    // simple: find users with overlapping styles and pick most popular destinations among them
    const similar = users.filter((u) => {
      if (!u.profile || !profile) return false;
      const a = u.profile.styles || [];
      const b = profile.styles || [];
      return a.some((x) => b.includes(x));
    });

    const counts = {};
    similar.forEach((u) => {
      (u.saved || []).forEach((id) => { counts[id] = (counts[id] || 0) + 1; });
    });

    const ranked = Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([id])=>id);
    const found = ranked.map((id) => allDestinations.find((d) => d.id === id)).filter(Boolean);
    // fallback to content-based if no collaborative info
    if (found.length === 0) return recommendContent(profile, allDestinations, top);
    return found.slice(0, top);
  } catch (e) {
    return recommendContent(profile, allDestinations, top);
  }
}

export default { recommendContent, recommendCollaborative };
