import React, { useState, useEffect } from 'react';

export default function Filters({ initialBudget = 50000, onBudgetChange, onClear, onFilterChange }) {
  const [budget, setBudget] = useState(initialBudget);
  const [selectedStyles, setSelectedStyles] = useState([]);

  useEffect(() => {
    if (onBudgetChange) onBudgetChange(budget);
  }, [budget, onBudgetChange]);

  useEffect(() => {
    if (onFilterChange) onFilterChange({ budget, styles: selectedStyles });
  }, [budget, selectedStyles, onFilterChange]);

  function handleClear() {
    setBudget(50000);
    if (onClear) onClear();
  }

  function toggleStyle(s) {
    setSelectedStyles((prev) => {
      const found = prev.includes(s);
      const next = found ? prev.filter((x) => x !== s) : [...prev, s];
      return next;
    });
  }

  return (
    <aside className="filters">
      <div className="filters-panel">
        <h3>Budget Per Trip</h3>
        <div className="slider-wrap">
          <input
            aria-label="budget-slider"
            type="range"
            min={0}
            max={50000}
            step={500}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="range-slider"
          />
          <div className="slider-value">Up to {budget.toLocaleString()} PKR</div>
        </div>

        <h4 style={{ marginTop: 12 }}>Travel Style</h4>
        <div className="filter-list">
          {['Adventure','Nature','Luxury','Historical','Family','Solo','City','Relaxation'].map((s) => (
            <label key={s}><input type="checkbox" checked={selectedStyles.includes(s)} onChange={() => toggleStyle(s)} /> {s}</label>
          ))}
        </div>

  <button className="btn-outline" style={{ marginTop: 12 }} onClick={() => { handleClear(); setSelectedStyles([]); if (onFilterChange) onFilterChange({ budget:50000, styles: [] }); }}>Clear Filters</button>
      </div>
    </aside>
  );
}
