import React from 'react';
import { estimateTripCost } from '../utils/cost';

export default function CostSummary({ dest, duration = 3 }) {
  const c = estimateTripCost(dest, duration);

  return (
    <div className="cost-summary">
      <h4>Estimated Cost (approx.)</h4>
      <table>
        <tbody>
          <tr><td>Hotel ({duration} nights)</td><td>Rs. {c.hotel.toLocaleString()}</td></tr>
          <tr><td>Food ({duration} days)</td><td>Rs. {c.food.toLocaleString()}</td></tr>
          <tr><td>Travel & transfers</td><td>Rs. {c.travel.toLocaleString()}</td></tr>
          <tr className="subtotal"><td>Tax & fees</td><td>Rs. {c.tax.toLocaleString()}</td></tr>
          <tr className="total"><td>Total</td><td>Rs. {c.total.toLocaleString()}</td></tr>
        </tbody>
      </table>
    </div>
  );
}
