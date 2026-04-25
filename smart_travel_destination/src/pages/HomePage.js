import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import DestinationCard from '../components/DestinationCard';
import { useAuth } from '../context/AuthContext';
import { getApiBase } from '../api/client';

export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [home, setHome] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const [searchExtract, setSearchExtract] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const q = user && user.id ? `?user_id=${user.id}` : '';
    fetch(`${getApiBase()}/api/home${q}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setHome(data);
      })
      .catch(() => {
        if (!cancelled) setHome({ greeting: 'Welcome!', featured: [], suggestions: [], weather: {}, travel_advisory: '' });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  function handleSearch(q) {
    setSearchLoading(true);
    fetch(`${getApiBase()}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, user_id: user ? user.id : null }),
    })
      .then((r) => r.json())
      .then((data) => {
        setSearchResults(data.destinations || []);
        const ex = data.extracted || null;
        setSearchExtract(ex);
        if (ex && (ex.duration_days != null || ex.budget_pkr != null)) {
          try {
            sessionStorage.setItem(
              'st_search_query_plan',
              JSON.stringify({
                days: ex.duration_days > 0 ? ex.duration_days : 3,
                totalBudgetPkr: ex.budget_pkr != null ? ex.budget_pkr : null,
              })
            );
          } catch (e) {
            // ignore
          }
        }
      })
      .catch(() => {
        setSearchResults([]);
        setSearchExtract(null);
      })
      .finally(() => setSearchLoading(false));
  }

  const greeting = home && home.greeting ? home.greeting : 'Welcome!';

  return (
    <div className="page page-home">
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-top">{loading ? 'Loading…' : greeting}</div>
          <h1 className="hero-title">Discover Your Perfect Destination</h1>
          <p className="hero-sub">
            Let AI help you plan personalized trips based on your preferences, budget, and interests
          </p>

          <SearchBar onSearch={handleSearch} />

          <div className="hero-chips">
            {(home && home.suggestions
              ? home.suggestions
              : [
                  'Ideal weekend destinations this month in northern Pakistan',
                  'Best budget trips under 20,000 PKR',
                  'Top-rated adventure places near Islamabad',
                ]
            ).map((s) => (
              <button key={s} type="button" className="chip" onClick={() => handleSearch(s)}>
                {s}
              </button>
            ))}
          </div>

          <div style={{ marginTop: 16 }}>
            <button type="button" className="btn" onClick={() => navigate('/explore')}>
              Plan My Trip
            </button>
          </div>
        </div>
      </section>

      {searchLoading && <p className="muted">Searching…</p>}

      {searchResults && searchResults.length > 0 && (
        <section className="search-results">
          <div className="section-meta">
            <div className="ai-banner">AI-Powered Search Results</div>
            <h2>{searchResults.length} Destinations Found</h2>
            <p className="muted">Based on your query (NLP via Groq when API key is set)</p>
          </div>

          <div className="cards-grid explore-grid">
            {searchResults.map((d) => (
              <DestinationCard key={d.id} dest={d} queryPlan={searchExtract} />
            ))}
          </div>
        </section>
      )}

      {home && home.weather && (
        <div className="summary-row">
          <div className="summary-card">
            <div className="kicker">Weather highlight</div>
            <h3>{home.weather.location || 'Islamabad'}</h3>
            <div className="muted">
              {home.weather.summary}
              {home.weather.temp_c != null ? ` · ${home.weather.temp_c}°C` : ''}
              {home.weather.feels_c != null && home.weather.temp_c != null
                ? ` (feels ${home.weather.feels_c}°C)`
                : ''}
            </div>
          </div>
          <div className="summary-card">
            <div className="kicker">Travel advisory</div>
            <h3>Stay informed</h3>
            <div className="muted small">{home.travel_advisory}</div>
          </div>
          <div className="summary-card">
            <div className="kicker">Quick action</div>
            <h3>Saved trips</h3>
            <div className="muted">
              <button type="button" className="btn-outline small" onClick={() => navigate('/trips')}>
                View plans
              </button>
            </div>
          </div>
        </div>
      )}

      <section className="featured">
        <div className="section-head">
          <h2>Featured Destinations</h2>
          <button type="button" className="btn-outline small" onClick={() => navigate('/explore')}>
            View All
          </button>
        </div>

        <div className="cards-grid featured-grid">
          {(home && home.featured ? home.featured : []).map((d) => (
            <DestinationCard key={d.id} dest={d} />
          ))}
        </div>
      </section>
    </div>
  );
}
