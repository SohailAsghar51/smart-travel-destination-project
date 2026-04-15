import React, { useState, useEffect, useRef } from 'react';
import destinationsData from '../data/destinations.json';
import DestinationCard from '../components/DestinationCard';
import Filters from '../components/Filters';
import SearchBar from '../components/SearchBar';

export default function ExplorePage() {
  const [budget, setBudget] = useState(50000);
  const [styles, setStyles] = useState([]);
  const [results, setResults] = useState(destinationsData);

  useEffect(() => {
    // initialize results with current filters (none)
    setResults(destinationsData);
  }, []);

  function matchesStyles(dest, stylesList) {
    if (!stylesList || stylesList.length === 0) return true;
    return stylesList.some((st) => {
      const lower = st.toLowerCase();
      return (dest.type && dest.type.toLowerCase() === lower) || (dest.tags && dest.tags.map(t => t.toLowerCase()).includes(lower));
    });
  }

  function applyFilters(q, b, s) {
    const t = q ? q.toLowerCase() : '';
    const filtered = destinationsData.filter((d) => {
      const matchesText = !t || d.name.toLowerCase().includes(t) || d.region.toLowerCase().includes(t) || d.tags.join(' ').toLowerCase().includes(t);
      const matchesBudget = (typeof b === 'number') ? d.priceFrom <= b : true;
      const matchesStyle = matchesStyles(d, s);
      return matchesText && matchesBudget && matchesStyle;
    });
    setResults(filtered);
  }

  function handleBudgetChange(b) {
    setBudget(b);
    applyFilters('', b, styles);
  }

  function handleSearch(q) {
    setQueryRef(q);
    applyFilters(q, budget, styles);
  }

  function handleFilterChange({ budget: b, styles: s }) {
    if (typeof b !== 'undefined') setBudget(b);
    setStyles(s || []);
    applyFilters(queryRef.current, (typeof b !== 'undefined' ? b : budget), s || []);
  }

  // small ref to keep latest query for filter interplay
  const queryRef = useRef('');
  function setQueryRef(q) { queryRef.current = q; }

  return (
    <div className="page page-explore layout-two-col">
      <div className="explore-left">
        <Filters initialBudget={budget} onBudgetChange={handleBudgetChange} onFilterChange={handleFilterChange} onClear={() => { setResults(destinationsData); setStyles([]); setBudget(50000); }} />
      </div>

      <div className="explore-right">
        <div className="explore-header">
          <SearchBar onSearch={handleSearch} placeholder={'Best budget trips under 20,000 PKR'} />
        </div>

        <div className="section-meta">
          <div className="ai-banner">AI-Powered Search Results</div>
          <h2>{results.length} Destinations Found</h2>
          <p className="muted">Based on your preferences and search criteria</p>
        </div>

        <div className="cards-grid explore-grid">
          {results.map((d) => (
            <DestinationCard key={d.id} dest={d} />
          ))}
        </div>
      </div>
    </div>
  );
}
