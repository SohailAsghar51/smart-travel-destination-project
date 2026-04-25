import React, { useState } from 'react';
import CostSummary from './CostSummary';

const DEFAULT_DEST_HERO =
  'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60';

export default function DestinationModal({ dest, onClose }) {
  const [days, setDays] = useState(3);
  const heroUrl = dest.image || dest.image_url || DEFAULT_DEST_HERO;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <div className="modal-grid">
          <div className="modal-image" style={{ backgroundImage: `url(${heroUrl})` }} />
          <div className="modal-body">
            <h2>{dest.name}</h2>
            <div className="muted">{dest.region} • {dest.type}</div>

            <div style={{ marginTop: 12 }}>
              <label>Duration (days)</label>
              <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={7}>7</option>
              </select>
            </div>

            <div style={{ marginTop: 12 }}>
              <h4>Trip summary</h4>
              <p className="muted">{dest.summary || `${dest.type} trip in ${dest.region}. Best season: ${dest.best_season}.`}</p>
            </div>

            <div style={{ marginTop: 12 }}>
              <CostSummary dest={dest} duration={days} />
            </div>

            <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
              <button className="btn" onClick={() => { alert('Itinerary generated (mock).'); }}>Generate Itinerary</button>
              <button className="btn-outline" onClick={onClose}>Close</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
