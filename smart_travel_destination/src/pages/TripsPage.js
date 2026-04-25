import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import DestinationCard from '../components/DestinationCard';
import { useNavigate, Link } from 'react-router-dom';
import { apiUrl } from '../api/client';

const DEFAULT_TRIP_THUMB =
  'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=400&q=60';

export default function TripsPage() {
  const { user } = useAuth();
  const [savedDestinations, setSavedDestinations] = useState([]);
  const [trips, setTrips] = useState([]);
  const navigate = useNavigate();
  const userId = user ? user.id : null;

  useEffect(() => {
    if (!userId) {
      setSavedDestinations([]);
      setTrips([]);
      return;
    }
    fetch(apiUrl(`/api/favorites/${userId}`))
      .then((r) => r.json())
      .then((data) => setSavedDestinations(data.favorites || []))
      .catch(() => setSavedDestinations([]));
    fetch(`${apiUrl('/api/trips')}?user_id=${userId}`)
      .then((r) => r.json())
      .then((data) => setTrips(data.trips || []))
      .catch(() => setTrips([]));
  }, [userId]);

  return (
    <div className="page page-trips">
      <h1>Your travel</h1>
      {user ? (
        <>
          <h2 className="section-title" style={{ marginTop: 16 }}>Planned trips</h2>
          <p className="lead muted">Itineraries you saved (stored in the database).</p>
          {trips.length === 0 ? (
            <div className="empty">No saved plans yet. Open a destination, review the plan, and click &ldquo;Save to my trips&rdquo;.</div>
          ) : (
            <ul className="trip-list" style={{ listStyle: 'none', padding: 0 }}>
              {trips.map((t) => (
                <li key={t.id} className="trip-list-item">
                  <Link to={`/trips/saved/${t.id}`} className="trip-list-link">
                    <span
                      className="trip-list-thumb"
                      style={{
                        backgroundImage: `url(${t.image || t.image_url || DEFAULT_TRIP_THUMB})`,
                      }}
                      role="img"
                      aria-hidden
                    />
                    <span className="trip-list-title">{t.title}</span>
                    <span className="trip-list-meta muted">
                      {t.region || 'Pakistan'}
                      {t.duration_days != null && ` · ${t.duration_days} day(s)`}
                      {t.estimated_cost_pkr != null && ` · ~${t.estimated_cost_pkr.toLocaleString()} PKR`}
                    </span>
                    <span className="trip-list-chew">View plan →</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <h2 className="section-title" style={{ marginTop: 24 }}>Saved destinations</h2>
          <p className="lead">Places you favorited (favorite_destinations table).</p>
          {savedDestinations.length === 0 ? (
            <div className="empty">You have not saved any destinations yet. Browse and click &ldquo;Save&rdquo;.</div>
          ) : (
            <div className="cards-grid">
              {savedDestinations.map((d) => (
                <DestinationCard key={d.id} dest={d} />
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="empty">
          <p className="lead">You are not signed in.</p>
          <p>Please sign in to view and manage your saved plans.</p>
          <div style={{ marginTop: 12 }}>
            <button type="button" className="btn" onClick={() => navigate('/login')}>
              Sign in
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
