import React, { useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiBase } from '../api/client';

const SAVED_TRIP_HERO_FALLBACK =
  'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60';

function itemTypeLabel(t) {
  if (!t) return '';
  const m = { hotel: 'Stay', restaurant: 'Eat', attraction: 'See & do', transport: 'Move' };
  return m[t] || t;
}

export default function SavedTripPage() {
  const { tripId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.id) {
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    setError('');
    setLoading(true);
    fetch(`${getApiBase()}/api/trips/${tripId}?user_id=${user.id}`, { signal: ac.signal })
      .then(async (r) => {
        const j = await r.json();
        if (r.status === 404) {
          setError(j.message || 'Trip not found.');
          setData(null);
          return;
        }
        if (!r.ok) {
          setError(j.message || 'Could not load trip.');
          setData(null);
          return;
        }
        setData(j);
      })
      .catch((e) => {
        if (e.name === 'AbortError') return;
        setError('Network error.');
        setData(null);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, [tripId, user?.id]);

  if (!user) {
    return (
      <div className="page plan-page">
        <p>Sign in to view saved trips.</p>
        <button type="button" className="btn" onClick={() => navigate('/login')}>
          Sign in
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page plan-page">
        <p className="muted">Loading your saved plan…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page plan-page">
        <p className="plan-error-banner">{error || 'No data'}</p>
        <Link to="/trips">← Back to your travel</Link>
      </div>
    );
  }

  const { trip, cost_breakdown, itinerary, trip_meta } = data;
  const displayPlan = itinerary || [];
  const destId = trip.destination_id;
  const heroUrl = trip.image || trip.image_url || SAVED_TRIP_HERO_FALLBACK;

  return (
    <div className="page plan-page">
      <div className="saved-trip-back">
        <Link to="/trips" className="saved-trip-back-link">
          ← Your travel
        </Link>
      </div>

      <div className="plan-hero saved-trip-hero">
        <div className="plan-hero-image" style={{ backgroundImage: `url(${heroUrl})` }} />
        <div className="plan-hero-text">
          <h1 className="saved-trip-title">{trip.title}</h1>
          <p className="plan-hero-sub muted">
            {trip.destination_name} · {trip.region}
            {typeof trip.duration_days === 'number' && ` · ${trip.duration_days} day(s)`}
          </p>
          {trip_meta?.label && (
            <p className="plan-label-line" style={{ marginTop: 4 }}>
              {trip_meta.label}
            </p>
          )}
          {destId != null && (
            <p style={{ marginTop: 8 }}>
              <Link to={`/trip/${destId}`} className="plan-map-link">
                Open destination page (new plan or preview)
              </Link>
            </p>
          )}
        </div>
      </div>

      <div className="saved-trip-costs">
        <h2 className="saved-trip-h2">Costs (saved)</h2>
        <div className="saved-cost-grid">
          <div className="saved-cost-tile">
            <span className="saved-cost-label">Budget (total)</span>
            <span className="saved-cost-value">
              {trip.total_budget_pkr != null
                ? `${Number(trip.total_budget_pkr).toLocaleString()} PKR`
                : '—'}
            </span>
          </div>
          <div className="saved-cost-tile">
            <span className="saved-cost-label">Estimated total</span>
            <span className="saved-cost-value">
              {Number(trip.estimated_cost_pkr || 0).toLocaleString()} PKR
            </span>
          </div>
        </div>
        {cost_breakdown && (
          <table className="saved-breakdown cost-summary" style={{ marginTop: 12, maxWidth: 480 }}>
            <tbody>
              <tr>
                <td>Transport</td>
                <td>{cost_breakdown.transport_cost_pkr.toLocaleString()} PKR</td>
              </tr>
              <tr>
                <td>Accommodation</td>
                <td>{cost_breakdown.accommodation_cost_pkr.toLocaleString()} PKR</td>
              </tr>
              <tr>
                <td>Food</td>
                <td>{cost_breakdown.food_cost_pkr.toLocaleString()} PKR</td>
              </tr>
              <tr>
                <td>Activities</td>
                <td>{cost_breakdown.activities_cost_pkr.toLocaleString()} PKR</td>
              </tr>
              <tr className="total">
                <td>Total (line items)</td>
                <td>{cost_breakdown.total_estimated_cost_pkr.toLocaleString()} PKR</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      <h2 className="saved-trip-h2" style={{ marginTop: 28 }}>Itinerary</h2>
      {displayPlan.length === 0 && <p className="muted">No day rows stored for this trip.</p>}
      <div className="plan-day-list" style={{ marginTop: 12 }}>
        {displayPlan.map((day) => (
          <article key={day.day_number} className="plan-day-card">
            <header className="plan-day-header">
              <span className="plan-day-index">Day {day.day_number}</span>
              {day.day_title && <h2 className="plan-day-title">{day.day_title}</h2>}
            </header>
            {day.day_summary && <p className="plan-day-summary">{day.day_summary}</p>}
            {day.estimated_day_cost_pkr > 0 && (
              <p className="muted small" style={{ marginTop: 6 }}>
                Day subtotal: ~{Number(day.estimated_day_cost_pkr).toLocaleString()} PKR
              </p>
            )}
            <ul className="plan-blocks">
              {(day.items || []).map((line, idx) => {
                const timeLine =
                  line.start_time && line.end_time
                    ? `${line.start_time} – ${line.end_time}`
                    : line.start_time || null;
                const itype = (line.item_type || '').toLowerCase();
                return (
                  <li key={`${day.day_number}-${idx}-${line.sequence_number}`} className={`plan-block plan-block--${itype || 'other'}`}>
                    <div className="plan-block-top">
                      {timeLine && <span className="plan-block-time">{timeLine}</span>}
                      {itype && <span className="plan-block-badge">{itemTypeLabel(itype)}</span>}
                    </div>
                    <h3 className="plan-block-name">
                      {line.title}
                      {line.place_name && !(line.title || '').includes(line.place_name) && (
                        <span className="muted small"> — {line.place_name}</span>
                      )}
                    </h3>
                    {line.description && <p className="plan-block-desc">{line.description}</p>}
                    <div className="plan-block-meta">
                      {line.place_address && <span className="plan-block-addr">{line.place_address}</span>}
                      {line.estimated_cost_pkr > 0 && (
                        <span className="plan-block-cost">≈ {line.estimated_cost_pkr.toLocaleString()} PKR</span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
