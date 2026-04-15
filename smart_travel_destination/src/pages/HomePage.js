import React, { useState } from 'react';
import SearchBar from '../components/SearchBar';
import DestinationCard from '../components/DestinationCard';
import Suggestions from '../components/Suggestions';
import destinationsData from '../data/destinations.json';
import parseQuery from '../utils/parseQuery';

export default function HomePage() {
  const [parsed, setParsed] = useState(null);
  const [results, setResults] = useState([]);

  function handleSearch(q) {
    const p = parseQuery(q);
    setParsed(p);

    const matches = destinationsData.filter((d) => {
      if (p.destination) {
        return d.name.toLowerCase().includes(p.destination.toLowerCase()) ||
               d.region.toLowerCase().includes(p.destination.toLowerCase());
      }
      if (p.budget) {
        return d.priceFrom <= p.budget;
      }
      return true;
    });

    setResults(matches.slice(0, 6));
  }

  return (
    <div className="page page-home">
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-top">Welcome back, Amna! Ready for your next adventure?</div>
          <h1 className="hero-title">Discover Your Perfect Destination</h1>
          <p className="hero-sub">Let AI help you plan personalized trips based on your preferences, budget, and interests</p>

          <SearchBar onSearch={handleSearch} />

          <div className="hero-chips">
            <button className="chip" onClick={() => handleSearch('Ideal weekend destinations this month')}>Ideal weekend destinations this month</button>
            <button className="chip" onClick={() => handleSearch('Best budget trips under 20,000 PKR')}>Best budget trips under 20,000 PKR</button>
            <button className="chip" onClick={() => handleSearch('Top-rated adventure places near you')}>Top-rated adventure places near you</button>
          </div>
        </div>
      </section>

      {/* Show search results if any */}
      {results && results.length > 0 && (
        <section className="search-results">
          <div className="section-meta">
            <div className="ai-banner">AI-Powered Search Results</div>
            <h2>{results.length} Destinations Found</h2>
            <p className="muted">Based on your query</p>
          </div>

          <div className="cards-grid explore-grid">
            {results.map((d) => (
              <DestinationCard key={d.id} dest={d} />
            ))}
          </div>
        </section>
      )}

      <div className="summary-row">
        <div className="summary-card">
          <div className="kicker">Popular This Week</div>
          <h3>Hunza Valley</h3>
          <div className="muted">+15% bookings</div>
        </div>
        <div className="summary-card">
          <div className="kicker">Average Budget</div>
          <h3>25,000 PKR</h3>
          <div className="muted">For 3-day trips</div>
        </div>
        <div className="summary-card">
          <div className="kicker">Best Season Now</div>
          <h3>Summer</h3>
          <div className="muted">Perfect weather</div>
        </div>
      </div>

      <section className="featured">
        <div className="section-head">
          <h2>Featured Destinations</h2>
          <button className="btn-outline small">View All</button>
        </div>

        <div className="cards-grid featured-grid">
          {destinationsData.slice(0,3).map((d) => (
            <DestinationCard key={d.id} dest={d} />
          ))}
        </div>
      </section>
    </div>
  );
}
