import React, { useState, useEffect, useCallback } from 'react';
import { apiUrl } from '../api/client';

/** Human-readable label; DB stores lowercase (e.g. cultural → Cultural, hill station → Hill Station). */
export function formatCategoryLabel(slug) {
  if (!slug) return '';
  return String(slug)
    .split(/[\s,_-]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

const DEFAULT_BUDGET_MAX = 50000;

export default function Filters({
  initialBudget = DEFAULT_BUDGET_MAX,
  onClear,
  onFilterChange,
}) {
  const [budget, setBudget] = useState(initialBudget);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [dbCategories, setDbCategories] = useState([]);
  const [catLoading, setCatLoading] = useState(true);
  const [catError, setCatError] = useState('');

  // Load category names from the database once (same list the server uses for filters)
  useEffect(() => {
    setCatLoading(true);
    setCatError('');
    fetch(apiUrl('/api/destination-categories'))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        const list = Array.isArray(data?.categories) ? data.categories : [];
        setDbCategories(list);
      })
      .catch(() => {
        setDbCategories([]);
        setCatError('Could not load categories');
      })
      .finally(() => setCatLoading(false));
  }, []);

  // Tell the Explore page when budget or categories change (one update, no infinite loop)
  useEffect(() => {
    if (onFilterChange) onFilterChange({ budget, styles: selectedCategories });
  }, [budget, selectedCategories, onFilterChange]);

  const handleClear = useCallback(() => {
    setBudget(DEFAULT_BUDGET_MAX);
    setSelectedCategories([]);
    if (onClear) onClear();
    if (onFilterChange) onFilterChange({ budget: DEFAULT_BUDGET_MAX, styles: [] });
  }, [onClear, onFilterChange]);

  function toggleCategory(value) {
    setSelectedCategories((prev) => {
      const v = String(value).toLowerCase();
      const found = prev.map((x) => String(x).toLowerCase()).includes(v);
      if (found) {
        return prev.filter((x) => String(x).toLowerCase() !== v);
      }
      return [...prev, v];
    });
  }

  return (
    <aside className="filters">
      <div className="filters-panel">
        <h3>Max. daily cost (PKR)</h3>
        <p className="muted small" style={{ margin: '0 0 8px' }}>
          Matches each destination&rsquo;s average cost per day (the amount shown on cards as / day).
        </p>
        <div className="slider-wrap">
          <input
            aria-label="budget-slider"
            type="range"
            min={0}
            max={DEFAULT_BUDGET_MAX}
            step={500}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="range-slider"
          />
          <div className="slider-value">Up to {budget.toLocaleString()} PKR / day</div>
        </div>

        <h4 style={{ marginTop: 12 }}>Category</h4>
        <p className="muted small" style={{ margin: '0 0 6px' }}>
          Loaded from the database: every distinct category in use for active destinations.
        </p>
        {catLoading && <p className="muted small">Loading…</p>}
        {catError && <p className="error small" style={{ margin: '0 0 6px' }}>{catError}</p>}
        <div className="filter-list">
          {!catLoading &&
            dbCategories.map((c) => (
              <label key={c}>
                <input
                  type="checkbox"
                  checked={selectedCategories.map((x) => String(x).toLowerCase()).includes(String(c).toLowerCase())}
                  onChange={() => toggleCategory(c)}
                />
                {formatCategoryLabel(c)}
              </label>
            ))}
        </div>

        <button type="button" className="btn-outline" style={{ marginTop: 12 }} onClick={handleClear}>
          Clear filters
        </button>
      </div>
    </aside>
  );
}
