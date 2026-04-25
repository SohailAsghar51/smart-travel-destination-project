import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

function planQueryFromExtract(ex) {
  if (!ex) return { days: 3, totalBudgetPkr: null };
  const days =
    ex.duration_days != null && Number(ex.duration_days) > 0 && Number(ex.duration_days) <= 30
      ? Number(ex.duration_days)
      : 3;
  const totalBudgetPkr = ex.budget_pkr != null && Number(ex.budget_pkr) > 0 ? Number(ex.budget_pkr) : null;
  return { days, totalBudgetPkr };
}

export default function DestinationCard({ dest, queryPlan }) {
  const { user, toggleSaveTrip } = useAuth();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user) {
      setSaved((user.saved || []).includes(String(dest.id)));
    } else {
      setSaved(false);
    }
  }, [user, dest.id]);

  async function handleToggleSave() {
    if (!user) {
      try {
        localStorage.setItem('pending_save', JSON.stringify({ id: dest.id, redirect: window.location.pathname }));
      } catch (e) {}
      navigate('/login');
      return;
    }

    const next = await toggleSaveTrip(dest.id);
    if (Array.isArray(next)) {
      setSaved(next.includes(String(dest.id)));
    } else {
      setSaved((s) => !s);
    }
  }

  const navigate = useNavigate();

  function goPlan() {
    let days = 3;
    let totalBudgetPkr = null;
    if (queryPlan) {
      const p = planQueryFromExtract(queryPlan);
      days = p.days;
      totalBudgetPkr = p.totalBudgetPkr;
    } else {
      try {
        const raw = sessionStorage.getItem('st_search_query_plan');
        if (raw) {
          const c = JSON.parse(raw);
          if (c.days) days = Math.min(30, Math.max(1, Number(c.days)));
          if (c.totalBudgetPkr != null) totalBudgetPkr = Number(c.totalBudgetPkr);
        }
      } catch (e) {
        // use defaults
      }
    }
    const qs = new URLSearchParams();
    qs.set('days', String(days));
    if (totalBudgetPkr != null) qs.set('total_budget_pkr', String(totalBudgetPkr));
    navigate(`/trip/${dest.id}?${qs.toString()}`);
  }

  const heroUrl =
    dest.image ||
    dest.image_url ||
    'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60';

  return (
    <>
    <article className="card featured-card">
      <div className="card-hero" style={{ backgroundImage: `url(${heroUrl})` }}>
        <div className="rating-badge">{dest.user_rating?.toFixed(1) || '—'}</div>
      </div>

      <div className="card-body">
        <div className="card-row">
          <div>
            <h3 className="card-title">{dest.name}</h3>
            <div className="card-sub">{dest.region}</div>
          </div>
          <div className="price-block">
            <div className="price">{dest.cost ? `Rs. ${dest.cost.toLocaleString()}` : ''}</div>
            <div className="per">/ day</div>
          </div>
        </div>

        <p className="card-summary">{dest.summary || `${dest.type} in ${dest.region}. Best in ${dest.best_season}.`}</p>

        <div className="card-tags">
          {(dest.tags || dest.activities || []).map((t) => (
            <span key={t} className="tag">{t}</span>
          ))}
        </div>

        <div className="card-actions">
          <button className="btn full" type="button" onClick={goPlan}>
            Plan Trip
          </button>
          <button className={saved ? 'btn saved' : 'btn-outline'} onClick={handleToggleSave} style={{ marginLeft: 8 }}>
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </div>
    </article>
    </>
  );
}
