// About: product story, features, and how Smart Travel works.
import React from 'react';
import { Link } from 'react-router-dom';

const features = [
  {
    title: 'Natural language search',
    text:
      'Describe the trip you want in plain language—budget, season, region, and style. We parse your intent and match it to destinations in the catalog.',
  },
  {
    title: 'Curated destinations',
    text:
      'Browse places across Pakistan with cost hints, climate, best seasons, and safety context so you can compare options at a glance.',
  },
  {
    title: 'Personalized recommendations',
    text:
      'When you are signed in, your travel profile and saved interests help shape suggestions and “for you” picks on the home experience.',
  },
  {
    title: 'Trips and itineraries',
    text:
      'Build multi-day plans with day-by-day items, place-backed stops, and cost estimates to keep the whole trip inside your budget.',
  },
  {
    title: 'Saved lists',
    text:
      'Keep favorite destinations in one place and return to them whenever you are ready to plan or book.',
  },
  {
    title: 'Weather and context',
    text:
      'Location-aware weather and seasonal notes help you time your visit and pack with confidence.',
  },
];

const steps = [
  {
    n: '1',
    title: 'Set your style',
    text: 'Create a profile with budget, duration, and the kinds of places you like—or explore as a guest.',
  },
  {
    n: '2',
    title: 'Search or browse',
    text: 'Use free-text search, filters on Explore, or start from featured picks on the home page.',
  },
  {
    n: '3',
    title: 'Plan and save',
    text: 'Open a destination, generate or refine a trip, and save it to revisit or share your ideas later.',
  },
];

function IconSearch() {
  return (
    <svg className="about-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
      />
    </svg>
  );
}

function IconMap() {
  return (
    <svg className="about-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"
      />
    </svg>
  );
}

function IconStar() {
  return (
    <svg className="about-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"
      />
    </svg>
  );
}

function IconTrip() {
  return (
    <svg className="about-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M20 6h-2.18c.11-.31.18-.65.18-1a2 2 0 0 0-2-2c-1.66 0-3 1.34-3 3H8c0-1.66-1.34-3-3-3S5 3.34 5 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-2 9h-3v3h-2v-3H8v-2h3V9h2v3h3v2z"
      />
    </svg>
  );
}

function IconHeart() {
  return (
    <svg className="about-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
      />
    </svg>
  );
}

function IconCloud() {
  return (
    <svg className="about-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z"
      />
    </svg>
  );
}

const featureIcons = [IconSearch, IconMap, IconStar, IconTrip, IconHeart, IconCloud];

export default function AboutPage() {
  return (
    <div className="page page-about">
      <header className="about-hero">
        <div className="about-hero-inner">
          <p className="about-badge">Why Smart Travel</p>
          <h1 className="about-title">Plan smarter trips across Pakistan</h1>
          <p className="about-lead">
            Smart Travel is a web app for discovering places, understanding costs and seasons, and turning ideas into
            day-by-day plans—whether you are planning a family holiday, a quiet escape, or your next adventure in the
            north.
          </p>
        </div>
      </header>

      <section className="about-section" aria-labelledby="about-mission">
        <h2 id="about-mission" className="about-h2">
          Our focus
        </h2>
        <p className="about-prose">
          We combine a structured database of destinations and points of interest with search and language models
          so you can go from a vague idea (“hills, two days, not too cold”) to a short list of real options.
          The goal is fewer tabs and less guesswork: one place to explore, compare, and start a concrete plan.
        </p>
      </section>

      <section className="about-section" aria-labelledby="about-features">
        <h2 id="about-features" className="about-h2">
          What you can do
        </h2>
        <div className="about-feature-grid">
          {features.map((f, i) => {
            const Ico = featureIcons[i] || IconSearch;
            return (
              <article key={f.title} className="about-feature-card">
                <div className="about-feature-icon" aria-hidden>
                  <Ico />
                </div>
                <h3 className="about-h3">{f.title}</h3>
                <p className="about-feature-text">{f.text}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="about-section about-how" aria-labelledby="about-how">
        <h2 id="about-how" className="about-h2">
          How it works
        </h2>
        <ol className="about-steps">
          {steps.map((s) => (
            <li key={s.n} className="about-step">
              <span className="about-step-n">{s.n}</span>
              <div>
                <h3 className="about-h3 about-step-title">{s.title}</h3>
                <p className="about-step-text">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>



      <section className="about-cta" aria-label="Get started">
        <h2 className="about-cta-title">Ready to explore?</h2>
        <p className="about-cta-text">Jump into search and filters, or open your profile to tune recommendations.</p>
        <div className="about-cta-actions">
          <Link to="/" className="btn">
            Discover
          </Link>
          <Link to="/explore" className="btn-outline">
            Explore map &amp; filters
          </Link>
        </div>
      </section>
    </div>
  );
}
