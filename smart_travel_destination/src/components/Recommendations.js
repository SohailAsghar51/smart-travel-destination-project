import React, { useEffect, useState } from 'react';
import DestinationCard from './DestinationCard';
import { getApiBase } from '../api/client';

export default function Recommendations({ userId, userProfile }) {
  const [list, setList] = useState([]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    fetch(`${getApiBase()}/api/recommendations/${userId}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled || !data.items) return;
        setList(
          data.items.map((x) => ({
            dest: x.destination,
            reason: x.reason,
          }))
        );
      })
      .catch(() => setList([]));
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (list.length === 0) {
    return <p className="muted">No recommendations yet. Save your travel preferences, then we score destinations for you (content-based).</p>;
  }

  return (
    <div className="recommendations">
      <p className="muted small" style={{ marginBottom: 8 }}>
        Scores come from a simple content-based model (your profile vs. destination cost, category, and rating).
      </p>
      <div className="cards-grid">
        {list.map((x) => (
          <DestinationCard key={x.dest.id} dest={x.dest} />
        ))}
      </div>
    </div>
  );
}
