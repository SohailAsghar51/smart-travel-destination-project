import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function DestinationCard({ dest }) {
  const { user, toggleSaveTrip } = useAuth();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setSaved((user.saved || []).includes(dest.id));
    } else {
      // When logged out, do not reflect guest-saved state in the UI — always show as not saved
      setSaved(false);
    }
  }, [user, dest.id]);

  function handleToggleSave() {
    if (!user) {
      // remember intent and send to login
      try {
        localStorage.setItem('pending_save', JSON.stringify({ id: dest.id, redirect: window.location.pathname }));
      } catch (e) {}
      navigate('/login');
      return;
    }

    const next = toggleSaveTrip(dest.id);
    // toggleSaveTrip returns new saved array for logged user or guest saved array
    if (Array.isArray(next)) {
      setSaved(next.includes(dest.id));
    } else {
      // for safety, flip
      setSaved((s) => !s);
    }
  }

  const navigate = useNavigate();

  return (
    <>
    <article className="card featured-card">
      <div className="card-hero" style={{ backgroundImage: `url(${dest.image})` }}>
        <div className="rating-badge">{dest.user_rating?.toFixed(1) || '—'}</div>
      </div>

      <div className="card-body">
        <div className="card-row">
          <div>
            <h3 className="card-title">{dest.name}</h3>
            <div className="card-sub">{dest.region}</div>
          </div>
          <div className="price-block">
            <div className="price">{dest.cost ? `Rs. ${dest.cost.toLocaleString()}` : ''}</div>
            <div className="per">/ day</div>
          </div>
        </div>

        <p className="card-summary">{dest.summary || `${dest.type} in ${dest.region}. Best in ${dest.best_season}.`}</p>

        <div className="card-tags">
          {(dest.tags || []).map((t) => (
            <span key={t} className="tag">{t}</span>
          ))}
        </div>

        <div className="card-actions">
          <button className="btn full" onClick={() => navigate(`/trip/${dest.id}?days=3`)}>Plan Trip</button>
          <button className={saved ? 'btn saved' : 'btn-outline'} onClick={handleToggleSave} style={{ marginLeft: 8 }}>
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </div>
    </article>
    </>
  );
}
