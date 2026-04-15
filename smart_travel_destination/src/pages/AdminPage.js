import React, { useState, useEffect } from 'react';
import { getAllDestinations, saveAllDestinations } from '../utils/data';

export default function AdminPage() {
  const [raw, setRaw] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    const list = getAllDestinations();
    setRaw(JSON.stringify(list, null, 2));
  }, []);

  function save() {
    try {
      const parsed = JSON.parse(raw);
      saveAllDestinations(parsed);
      setStatus('Saved to localStorage');
    } catch (e) {
      setStatus('Invalid JSON: ' + e.message);
    }
  }

  function resetToDefault() {
    localStorage.removeItem('admin_destinations');
    const list = getAllDestinations();
    setRaw(JSON.stringify(list, null, 2));
    setStatus('Reset to default (bundled)');
  }

  return (
    <div className="page page-admin">
      <h1>Admin — Manage Destinations</h1>
      <p className="muted">Edit the destinations JSON below and save. Changes persist to localStorage for the prototype.</p>
      <div style={{ marginTop: 12 }}>
        <textarea value={raw} onChange={(e) => setRaw(e.target.value)} style={{ width: '100%', height: 420 }} />
      </div>
      <div style={{ marginTop: 8 }}>
        <button className="btn" onClick={save}>Save</button>
        <button className="btn-outline" onClick={resetToDefault} style={{ marginLeft: 8 }}>Reset</button>
        <span style={{ marginLeft: 12 }}>{status}</span>
      </div>
    </div>
  );
}
