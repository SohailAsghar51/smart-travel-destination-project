import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { getAllDestinations } from '../utils/data';
import Recommendations from '../components/Recommendations';

export default function ProfilePage() {
  const { user, logout, updateProfile } = useAuth();
  const [profile, setProfile] = useState(user?.profile || { budget: 25000, styles: [], duration: 3 });

  useEffect(() => {
    setProfile(user?.profile || profile);
    // eslint-disable-next-line
  }, [user]);

  function toggleStyle(s) {
    const next = profile.styles.includes(s) ? profile.styles.filter((x) => x !== s) : [...profile.styles, s];
    setProfile({ ...profile, styles: next });
  }

  function save() {
    updateProfile(profile);
    alert('Profile saved (local only)');
  }

  if (!user) return <div className="page page-profile"><h2>Please sign in to view your profile</h2></div>;

  const all = getAllDestinations();

  return (
    <div className="page page-profile">
      <div className="profile-grid">
        <div className="profile-form">
          <h1>{user.name}</h1>
          <div className="muted">{user.email}</div>

          <h4 style={{ marginTop: 12 }}>Budget</h4>
          <input type="range" min={0} max={50000} value={profile.budget} onChange={(e) => setProfile({ ...profile, budget: Number(e.target.value) })} />
          <div className="muted">Up to {profile.budget.toLocaleString()} PKR</div>

          <h4 style={{ marginTop: 12 }}>Travel Styles</h4>
          <div className="filter-list">
            {['Adventure', 'Relaxation', 'Family', 'City', 'Nature'].map((s) => (
              <label key={s}><input type="checkbox" checked={profile.styles.includes(s)} onChange={() => toggleStyle(s)} /> {s}</label>
            ))}
          </div>

          <h4 style={{ marginTop: 12 }}>Typical Duration (days)</h4>
          <select value={profile.duration} onChange={(e) => setProfile({ ...profile, duration: Number(e.target.value) })}>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={5}>5</option>
            <option value={7}>7</option>
          </select>

          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={save}>Save Preferences</button>
            <button className="btn-outline" style={{ marginLeft: 8 }} onClick={() => logout()}>Sign out</button>
          </div>
        </div>

        <div className="profile-recs">
          <h3>Recommended for you</h3>
          <Recommendations userProfile={profile} allDestinations={all} />
        </div>
      </div>
    </div>
  );
}
