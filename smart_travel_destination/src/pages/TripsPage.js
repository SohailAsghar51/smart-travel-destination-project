import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getAllDestinations } from '../utils/data';
import DestinationCard from '../components/DestinationCard';
import { useNavigate } from 'react-router-dom';

export default function TripsPage() {
  const { user } = useAuth();
  const [savedDestinations, setSavedDestinations] = useState([]);
  const navigate = useNavigate();

  function loadSaved() {
    const all = getAllDestinations();
    // Only show saved trips for logged-in users. If user is not logged in, we intentionally
    // keep the saved list empty and prompt them to sign in.
    let ids = [];
    if (user) ids = user.saved || [];
    const found = ids.map((id) => all.find((d) => d.id === id)).filter(Boolean);
    setSavedDestinations(found);
  }

  useEffect(() => {
    loadSaved();

    function onStorage(e) {
      if (e.key === 'st_current_user' || e.key === 'st_users') {
        loadSaved();
      }
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
    // eslint-disable-next-line
  }, [user]);

  return (
    <div className="page page-trips">
      <h1>Saved Trips</h1>
      {user ? (
        <>
          <p className="lead">Destinations you've saved.</p>

          {savedDestinations.length === 0 ? (
            <div className="empty">You haven't saved any trips yet. Browse destinations and click "Save" to add them here.</div>
          ) : (
            <div className="cards-grid">
              {savedDestinations.map((d) => (
                <DestinationCard key={d.id} dest={{ ...d, summary: d.summary }} />
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="empty">
          <p className="lead">You're not signed in.</p>
          <p>Please sign in to view and manage your saved trips.</p>
          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => navigate('/login')}>Sign in</button>
          </div>
        </div>
      )}
    </div>
  );
}
