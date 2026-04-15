import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { getAllDestinations } from '../utils/data';
import CostSummary from '../components/CostSummary';
import { useAuth } from '../context/AuthContext';

export default function TripDetails() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [dest, setDest] = useState(null);
  const [days, setDays] = useState(Number(searchParams.get('days')) || 3);
  const { user, toggleSaveTrip } = useAuth();
  const navigate = useNavigate();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const all = getAllDestinations();
    const found = all.find((d) => d.id === id);
    setDest(found);
  }, [id]);

  useEffect(() => {
    if (!dest) return;
    if (user) setSaved((user.saved || []).includes(dest.id));
    else {
      // Do not reflect guest-saved state in the UI for logged-out users — keep as not saved
      setSaved(false);
    }
  }, [dest, user]);

  if (!dest) return <div className="page page-trip"><h2>Destination not found</h2></div>;

  function handleSave() {
    if (!user) {
      try {
        localStorage.setItem('pending_save', JSON.stringify({ id: dest.id, redirect: window.location.pathname }));
      } catch (e) {}
      navigate('/login');
      return;
    }

    toggleSaveTrip(dest.id);
    setSaved((s) => !s);
  }

  function generateItinerary() {
    // simple mock itinerary
    const daysCount = days;
    const items = [];
    for (let i=1;i<=daysCount;i++) {
      const activity = dest.activities[(i-1) % (dest.activities.length || 1)];
      items.push({ day: i, plan: `Day ${i}: ${activity} around ${dest.name}` });
    }
    return items;
  }

  const itinerary = generateItinerary();

  return (
    <div className="page page-trip">
      <div className="trip-header">
        <div className="trip-image" style={{ backgroundImage: `url(${dest.image})` }} />
        <div className="trip-meta">
          <h1>{dest.name}</h1>
          <div className="muted">{dest.region} • {dest.type}</div>
          <div style={{ marginTop: 8 }}>
            <button className={saved ? 'btn saved' : 'btn'} onClick={handleSave}>{saved ? 'Saved' : 'Save'}</button>
          </div>
        </div>
      </div>

      <div className="trip-body">
        <div className="trip-left">
          <h3>Overview</h3>
          <p className="muted">{dest.summary || dest.activities.join(', ')}</p>

          <h4 style={{ marginTop: 12 }}>Duration</h4>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={5}>5</option>
            <option value={7}>7</option>
          </select>

          <h4 style={{ marginTop: 12 }}>Itinerary</h4>
          <div className="itinerary">
            {itinerary.map((it) => (
              <div key={it.day} className="it-day">
                <strong>Day {it.day}</strong>
                <div className="muted">{it.plan}</div>
              </div>
            ))}
          </div>
        </div>

        <aside className="trip-right">
          <h3>Cost Estimate</h3>
          <CostSummary dest={dest} duration={days} />

          <div style={{ marginTop: 12 }}>
            <h4>Details</h4>
            <div className="muted">Best season: {dest.best_season}</div>
            <div className="muted">Weather: {dest.weather}</div>
            <div className="muted">User Rating: {dest.user_rating}</div>
          </div>
        </aside>
      </div>
    </div>
  );
}
