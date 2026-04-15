import React from 'react';
import { recommendContent, recommendCollaborative } from '../utils/recommend';
import DestinationCard from './DestinationCard';

export default function Recommendations({ userProfile, allDestinations }) {
  const content = recommendContent(userProfile, allDestinations, 6);
  const collab = recommendCollaborative(userProfile, allDestinations, 6);

  // merge unique (preferring collaborative results)
  const ids = new Set();
  const merged = [];
  collab.forEach((d) => { if (!ids.has(d.id)) { ids.add(d.id); merged.push(d); } });
  content.forEach((d) => { if (!ids.has(d.id)) { ids.add(d.id); merged.push(d); } });

  return (
    <div className="recommendations">
      <div className="cards-grid">
        {merged.map((d) => (
          <DestinationCard key={d.id} dest={{ ...d, pricePerDay: d.cost, summary: `${d.type} in ${d.region}. Best in ${d.best_season}.` }} />
        ))}
      </div>
    </div>
  );
}
