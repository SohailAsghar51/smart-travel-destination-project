import React, { useState } from 'react';

export default function SearchBar({ onSearch, placeholder = 'Try "Plan a 3-day trip to northern Pakistan under 25,000 PKR"' }) {
  const [value, setValue] = useState('');

  function submit(e) {
    e.preventDefault();
    if (onSearch) onSearch(value.trim());
  }

  return (
    <form className="search-bar-hero" onSubmit={submit}>
      <div className="search-left">
        <input
          className="search-input-hero"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          aria-label="search"
        />
        <button className="search-btn-hero" type="submit">Search</button>
      </div>
      <div className="search-actions">
        <button type="button" className="filters-btn">Filters</button>
      </div>
    </form>
  );
}
