// Admin-only: create destinations and places (hotels, restaurants, attractions).
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { apiUrl } from '../api/client';

export default function AdminPage() {
  const { user } = useAuth();
  const [destinations, setDestinations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [destForm, setDestForm] = useState({
    name: '',
    region: '',
    category: 'mountain',
    country: 'Pakistan',
    description: '',
    avg_cost_pkr: 20000,
    best_season: '',
    climate: '',
    latitude: '',
    longitude: '',
    image_url: '',
  });
  const [placeForm, setPlaceForm] = useState({
    destination_id: '',
    name: '',
    category: 'Hotel',
    main_type: 'hotel',
    description: '',
    latitude: '',
    longitude: '',
    cost_pkr: '',
    rating: '',
    address: '',
  });
  const [places, setPlaces] = useState([]);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  function loadDestinations() {
    setLoading(true);
    fetch(`${apiUrl('/api/destinations')}?limit=500`)
      .then((r) => r.json())
      .then((data) => {
        setDestinations(Array.isArray(data) ? data : []);
      })
      .catch(() => setDestinations([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadDestinations();
  }, []);

  useEffect(() => {
    const id = placeForm.destination_id;
    if (!id) {
      setPlaces([]);
      return;
    }
    let cancelled = false;
    fetch(apiUrl(`/api/destinations/${id}/places`))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled) setPlaces(data?.places || []);
      })
      .catch(() => {
        if (!cancelled) setPlaces([]);
      });
    return () => {
      cancelled = true;
    };
  }, [placeForm.destination_id]);

  async function submitDestination(e) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(apiUrl('/api/admin/destinations'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          name: destForm.name,
          region: destForm.region,
          category: destForm.category,
          country: destForm.country,
          description: destForm.description,
          avg_cost_pkr: parseInt(String(destForm.avg_cost_pkr), 10),
          best_season: destForm.best_season,
          climate: destForm.climate,
          latitude: parseFloat(destForm.latitude),
          longitude: parseFloat(destForm.longitude),
          image_url: destForm.image_url,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Failed');
      setMsg(`Destination created (id ${data.id}).`);
      loadDestinations();
      setPlaceForm((p) => ({ ...p, destination_id: String(data.id) }));
    } catch (ex) {
      setErr(ex.message);
    }
  }

  async function submitPlace(e) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    try {
      const body = {
        user_id: user.id,
        destination_id: parseInt(placeForm.destination_id, 10),
        name: placeForm.name,
        category: placeForm.category,
        main_type: placeForm.main_type,
        latitude: parseFloat(placeForm.latitude),
        longitude: parseFloat(placeForm.longitude),
        description: placeForm.description || undefined,
        address: placeForm.address || undefined,
      };
      if (placeForm.cost_pkr !== '' && placeForm.cost_pkr !== null) {
        body.cost_pkr = parseInt(String(placeForm.cost_pkr), 10);
      }
      if (placeForm.rating !== '' && placeForm.rating !== null) {
        body.rating = parseFloat(placeForm.rating);
      }
      const res = await fetch(apiUrl('/api/admin/places'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Failed');
      setMsg(`Place created (id ${data.id}).`);
      const r2 = await fetch(apiUrl(`/api/destinations/${placeForm.destination_id}/places`));
      const d2 = await r2.json();
      setPlaces(d2.places || []);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  if (!user) {
    return (
      <div className="page page-auth">
        <h1>Admin</h1>
        <p>
          Please <Link to="/login">sign in</Link> as an administrator.
        </p>
      </div>
    );
  }

  if (user.role !== 'admin') {
    return (
      <div className="page page-auth">
        <h1>Admin</h1>
        <p>This area is only for admin accounts.</p>
        <p>
          <Link to="/">Back home</Link>
        </p>
      </div>
    );
  }

  return (
    <div className="page page-admin">
      <h1>Admin</h1>
      <p className="text-muted">Add destinations and places (hotels, restaurants, attractions).</p>
      {msg && <div className="admin-flash-ok">{msg}</div>}
      {err && <div className="error">{err}</div>}

      <div className="admin-grid">
        <section className="admin-card">
          <h2>New destination</h2>
          <form className="auth-form" onSubmit={submitDestination}>
            <label>Name</label>
            <input
              value={destForm.name}
              onChange={(e) => setDestForm({ ...destForm, name: e.target.value })}
              required
            />
            <label>Region</label>
            <input
              value={destForm.region}
              onChange={(e) => setDestForm({ ...destForm, region: e.target.value })}
              required
            />
            <label>Category</label>
            <input
              value={destForm.category}
              onChange={(e) => setDestForm({ ...destForm, category: e.target.value })}
              required
            />
            <label>Country</label>
            <input
              value={destForm.country}
              onChange={(e) => setDestForm({ ...destForm, country: e.target.value })}
            />
            <label>Average cost (PKR / day)</label>
            <input
              type="number"
              min={0}
              value={destForm.avg_cost_pkr}
              onChange={(e) => setDestForm({ ...destForm, avg_cost_pkr: e.target.value })}
              required
            />
            <label>Latitude</label>
            <input
              value={destForm.latitude}
              onChange={(e) => setDestForm({ ...destForm, latitude: e.target.value })}
              required
            />
            <label>Longitude</label>
            <input
              value={destForm.longitude}
              onChange={(e) => setDestForm({ ...destForm, longitude: e.target.value })}
              required
            />
            <label>Description (optional)</label>
            <input
              value={destForm.description}
              onChange={(e) => setDestForm({ ...destForm, description: e.target.value })}
            />
            <label>Best season (optional)</label>
            <input
              value={destForm.best_season}
              onChange={(e) => setDestForm({ ...destForm, best_season: e.target.value })}
            />
            <label>Climate (optional)</label>
            <input
              value={destForm.climate}
              onChange={(e) => setDestForm({ ...destForm, climate: e.target.value })}
            />
            <label>Image URL (optional)</label>
            <input
              value={destForm.image_url}
              onChange={(e) => setDestForm({ ...destForm, image_url: e.target.value })}
            />
            <button className="btn" type="submit" disabled={loading}>
              Add destination
            </button>
          </form>
        </section>

        <section className="admin-card">
          <h2>Add place to destination</h2>
          <form className="auth-form" onSubmit={submitPlace}>
            <label>Destination</label>
            <select
              value={placeForm.destination_id}
              onChange={(e) => setPlaceForm({ ...placeForm, destination_id: e.target.value })}
              required
            >
              <option value="">— Select —</option>
              {destinations.map((d) => (
                <option key={d.id || d.db_id} value={d.db_id || d.id}>
                  {d.name} ({d.region})
                </option>
              ))}
            </select>
            <label>Name</label>
            <input
              value={placeForm.name}
              onChange={(e) => setPlaceForm({ ...placeForm, name: e.target.value })}
              required
            />
            <label>Category label</label>
            <input
              value={placeForm.category}
              onChange={(e) => setPlaceForm({ ...placeForm, category: e.target.value })}
              required
            />
            <label>Type</label>
            <select
              value={placeForm.main_type}
              onChange={(e) => setPlaceForm({ ...placeForm, main_type: e.target.value })}
            >
              <option value="hotel">Hotel</option>
              <option value="restaurant">Restaurant</option>
              <option value="attraction">Attraction</option>
            </select>
            <label>Latitude</label>
            <input
              value={placeForm.latitude}
              onChange={(e) => setPlaceForm({ ...placeForm, latitude: e.target.value })}
              required
            />
            <label>Longitude</label>
            <input
              value={placeForm.longitude}
              onChange={(e) => setPlaceForm({ ...placeForm, longitude: e.target.value })}
              required
            />
            <label>Cost (PKR, optional)</label>
            <input
              type="number"
              min={0}
              value={placeForm.cost_pkr}
              onChange={(e) => setPlaceForm({ ...placeForm, cost_pkr: e.target.value })}
            />
            <label>Rating 0–5 (optional)</label>
            <input
              type="number"
              min={0}
              max={5}
              step={0.1}
              value={placeForm.rating}
              onChange={(e) => setPlaceForm({ ...placeForm, rating: e.target.value })}
            />
            <label>Address (optional)</label>
            <input
              value={placeForm.address}
              onChange={(e) => setPlaceForm({ ...placeForm, address: e.target.value })}
            />
            <label>Description (optional)</label>
            <input
              value={placeForm.description}
              onChange={(e) => setPlaceForm({ ...placeForm, description: e.target.value })}
            />
            <button className="btn" type="submit" disabled={!placeForm.destination_id || loading}>
              Add place
            </button>
          </form>
          {placeForm.destination_id ? (
            <div className="admin-places-preview">
              <h3>Places in this destination ({places.length})</h3>
              <ul>
                {places.map((p) => (
                  <li key={p.id}>
                    {p.name} — {p.main_type}
                    {p.cost_pkr !== null && p.cost_pkr !== undefined ? ` · ${p.cost_pkr} PKR` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
