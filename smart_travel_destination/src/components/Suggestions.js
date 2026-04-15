import React from 'react';

function SuggestionItem({ title, subtitle }) {
  return (
    <div className="suggestion-item">
      <h4>{title}</h4>
      <p className="muted">{subtitle}</p>
    </div>
  );
}

export default function Suggestions({ budget }) {
  const budgetLabel = budget ? `under Rs. ${budget.toLocaleString()}` : 'budget-friendly';

  return (
    <div className="suggestions">
      <h3>Travel Suggestions</h3>
      <SuggestionItem title={`Top Adventure Spots ${budget ? `(under Rs. ${budget.toLocaleString()})` : ''}`} subtitle={`Handpicked adventure trips ${budgetLabel}`} />
      <SuggestionItem title={`Best Weekend Destinations Near You`} subtitle={`Quick getaways within a day or two`} />
      <SuggestionItem title={`Cultural & Scenic Picks`} subtitle={`Photogenic and cultural spots`} />
    </div>
  );
}
