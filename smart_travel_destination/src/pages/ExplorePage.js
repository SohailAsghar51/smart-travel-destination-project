import React, { useState, useEffect, useCallback } from 'react';
import DestinationCard from '../components/DestinationCard';
import Filters from '../components/Filters';
import SearchBar from '../components/SearchBar';
import { apiUrl } from '../api/client';

export default function ExplorePage() {
  const [budget, setBudget] = useState(50000);
  const [styles, setStyles] = useState([]);
  const [allDest, setAllDest] = useState([]);
  const [results, setResults] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [searchExtract, setSearchExtract] = useState(null);

  useEffect(() => {
    // Load many destinations once; we filter in the browser (search + sliders)
    fetch(`${apiUrl('/api/destinations')}?limit=200`)
      .then((r) => r.json())
      .then((data) => {
        setAllDest(data);
        setResults(data);
      })
      .catch(() => {
        setAllDest([]);
        setResults([]);
      });
  }, []);

  /** Each checkbox value is a lowercase category from the API list */
  function matchesDbCategories(dest, selected) {
    if (!selected || selected.length === 0) return true;
    const raw = (dest.category || '').toLowerCase().trim();
    const parts = raw
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean);
    const tags = (dest.tags || []).map((t) => String(t).toLowerCase());
    return selected.some((sel) => {
      const s = String(sel).toLowerCase().trim();
      if (!s) return false;
      if (raw === s) return true;
      if (parts.includes(s)) return true;
      if (tags.includes(s)) return true;
      return false;
    });
  }

  const applyFilters = useCallback(
    (q, b, s) => {
      const t = q ? q.toLowerCase() : '';
      const filtered = allDest.filter((d) => {
        const matchesText =
          !t ||
          d.name.toLowerCase().includes(t) ||
          (d.region && d.region.toLowerCase().includes(t)) ||
          (d.category && d.category.toLowerCase().includes(t)) ||
          (d.tags && d.tags.join(' ').toLowerCase().includes(t));
        const perDay = d.priceFrom != null ? d.priceFrom : d.cost;
        const matchesBudget = typeof b === 'number' ? perDay != null && perDay <= b : true;
        const matchesCat = matchesDbCategories(d, s);
        return matchesText && matchesBudget && matchesCat;
      });
      setResults(filtered);
    },
    [allDest]
  );

  const handleSearch = useCallback(
    (q) => {
      setSearchText(q);
      applyFilters(q, budget, styles);
      if (q && q.length >= 2) {
        fetch(apiUrl('/api/nlp/parse'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q }),
        })
          .then((r) => r.json())
          .then((data) => {
            if (data.extracted) {
              setSearchExtract(data.extracted);
              try {
                const ex = data.extracted;
                if (ex.duration_days != null || ex.budget_pkr != null) {
                  sessionStorage.setItem(
                    'st_search_query_plan',
                    JSON.stringify({
                      days: ex.duration_days > 0 ? ex.duration_days : 3,
                      totalBudgetPkr: ex.budget_pkr != null ? ex.budget_pkr : null,
                    })
                  );
                }
              } catch (e) {
                // ignore
              }
            }
          })
          .catch(() => setSearchExtract(null));
      } else {
        setSearchExtract(null);
      }
    },
    [applyFilters, budget, styles]
  );

  const handleFilterChange = useCallback(
    ({ budget: b, styles: s }) => {
      if (typeof b !== 'undefined') setBudget(b);
      setStyles(s || []);
      applyFilters(searchText, typeof b !== 'undefined' ? b : budget, s || []);
    },
    [applyFilters, searchText, budget]
  );

  return (
    <div className="page page-explore layout-two-col">
      <div className="explore-left">
        <Filters
          initialBudget={budget}
          onFilterChange={handleFilterChange}
          onClear={() => {
            setResults(allDest);
            setStyles([]);
            setBudget(50000);
            setSearchText('');
          }}
        />
      </div>

      <div className="explore-right">
        <div className="explore-header">
          <SearchBar onSearch={handleSearch} placeholder={'Best budget trips under 20,000 PKR'} />
        </div>

        <div className="section-meta">
          <div className="ai-banner">Destinations from database</div>
          <h2>{results.length} Destinations Found</h2>
          <p className="muted">Based on your preferences and search criteria</p>
        </div>

        <div className="cards-grid explore-grid">
          {results.map((d) => (
            <DestinationCard key={d.id} dest={d} queryPlan={searchExtract} />
          ))}
        </div>
      </div>
    </div>
  );
}
