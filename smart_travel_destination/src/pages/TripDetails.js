import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import CostSummary from '../components/CostSummary';
import { useAuth } from '../context/AuthContext';
import { apiUrl } from '../api/client';

function parseIntParam(n, def, min, max) {
  const v = Number(n);
  if (Number.isFinite(v) && v >= min && v <= max) return v;
  return def;
}

function useDebouncedValue(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

function itemTypeLabel(t) {
  if (!t) return '';
  const m = { hotel: 'Stay', restaurant: 'Eat', attraction: 'See & do', transport: 'Move' };
  return m[t] || t;
}

export default function TripDetails() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [dest, setDest] = useState(null);
  const [days, setDays] = useState(() => parseIntParam(searchParams.get('days'), 3, 1, 30));
  const [queryTotalBudget, setQueryTotalBudget] = useState(() => {
    const t = searchParams.get('total_budget_pkr');
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) && n > 0 ? n : null;
  });
  const { user, toggleSaveTrip } = useAuth();
  const navigate = useNavigate();
  const [saved, setSaved] = useState(false);
  const [aiPlan, setAiPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');
  const [saveStatus, setSaveStatus] = useState('');
  const [planNotes, setPlanNotes] = useState('');
  const notesDebounced = useDebouncedValue(planNotes, 650);
  const [hasReceivedPlan, setHasReceivedPlan] = useState(false);
  const [liveWeather, setLiveWeather] = useState(null);
  const [liveWeatherNote, setLiveWeatherNote] = useState('');

  const destIdNum = useMemo(() => (dest ? Number(dest.id) || dest.db_id : null), [dest]);

  useEffect(() => {
    setAiPlan(null);
    setHasReceivedPlan(false);
    setPlanError('');
  }, [destIdNum]);

  useEffect(() => {
    fetch(apiUrl(`/api/destinations/${id}`))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setDest(d))
      .catch(() => setDest(null));
  }, [id]);

  useEffect(() => {
    setDays(parseIntParam(searchParams.get('days'), 3, 1, 30));
    const t = searchParams.get('total_budget_pkr');
    if (t) {
      const n = Number(t);
      setQueryTotalBudget(Number.isFinite(n) && n > 0 ? n : null);
    } else {
      setQueryTotalBudget(null);
    }
  }, [id, searchParams]);

  useEffect(() => {
    if (!dest) return;
    if (user && user.saved) setSaved(user.saved.includes(String(dest.id)));
    else setSaved(false);
  }, [dest, user]);

  useEffect(() => {
    if (!dest) return;
    const lat = dest.latitude;
    const lon = dest.longitude;
    if (lat == null || lon == null) {
      setLiveWeather(null);
      setLiveWeatherNote('');
      return;
    }
    const ac = new AbortController();
    setLiveWeatherNote('Loading current weather…');
    fetch(`${apiUrl('/api/weather')}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`, {
      signal: ac.signal,
    })
      .then(async (r) => {
        const j = await r.json();
        if (ac.signal.aborted) return;
        if (r.ok && j.ok) {
          setLiveWeather(j);
          setLiveWeatherNote('');
        } else {
          setLiveWeather(null);
          setLiveWeatherNote(j.message || 'Live weather not available. Add RAPIDAPI_KEY to the backend .env.');
        }
      })
      .catch(() => {
        if (!ac.signal.aborted) {
          setLiveWeather(null);
          setLiveWeatherNote('');
        }
      });
    return () => ac.abort();
  }, [dest]);

  const autoHint = useMemo(() => {
    const totalBudgetPkr =
      queryTotalBudget != null && queryTotalBudget > 0
        ? queryTotalBudget
        : dest && dest.cost
          ? dest.cost * days
          : null;
    const perDay = totalBudgetPkr && days > 0 ? Math.round(totalBudgetPkr / days) : null;
    return [
      `Plan for ${days} day(s)`,
      totalBudgetPkr != null ? `total trip budget about ${totalBudgetPkr} PKR` : null,
      perDay != null ? `around ${perDay} PKR per day` : null,
    ]
      .filter(Boolean)
      .join('; ');
  }, [queryTotalBudget, days, dest]);

  useEffect(() => {
    if (!dest || destIdNum == null) return;
    const ac = new AbortController();
    setPlanError('');
    setPlanLoading(true);
    const totalBudgetPkr =
      queryTotalBudget != null && queryTotalBudget > 0
        ? queryTotalBudget
        : dest.cost
          ? dest.cost * days
          : null;
    const user_message = [notesDebounced.trim(), autoHint].filter(Boolean).join('. ');

    fetch(apiUrl('/api/trips/preview'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        destination_id: destIdNum,
        days,
        total_budget_pkr: totalBudgetPkr,
        user_message: user_message || undefined,
      }),
      signal: ac.signal,
    })
      .then(async (r) => {
        const j = await r.json();
        if (ac.signal.aborted) return;
        if (!r.ok) {
          setPlanError(j.message || 'Could not build a plan. Try again later.');
          return;
        }
        if (j.itinerary) {
          setAiPlan({
            itinerary: j.itinerary,
            map_image_url: j.map_image_url,
            trip_meta: j.trip_meta,
            estimated_total_pkr: j.estimated_total_pkr,
            places_used: j.places_used_in_plan,
            planner: j.planner,
            weather_advisory: j.weather_advisory,
            weather_snapshot: j.weather_snapshot,
          });
          setHasReceivedPlan(true);
        }
      })
      .catch((e) => {
        if (e.name === 'AbortError' || ac.signal.aborted) return;
        setPlanError('Network error. Check that the server is running.');
      })
      .finally(() => {
        if (!ac.signal.aborted) setPlanLoading(false);
      });

    return () => ac.abort();
  }, [dest, destIdNum, days, queryTotalBudget, notesDebounced, autoHint]);

  if (!dest) {
    return (
      <div className="page page-trip plan-page">
        <h2>{id ? 'Loading destination…' : 'Destination not found'}</h2>
      </div>
    );
  }

  const image =
    dest.image ||
    dest.image_url ||
    'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=60';

  async function handleSave() {
    if (!user) {
      try {
        localStorage.setItem('pending_save', JSON.stringify({ id: dest.id, redirect: window.location.pathname }));
      } catch (e) {}
      navigate('/login');
      return;
    }

    const list = await toggleSaveTrip(dest.id);
    if (list) setSaved(list.includes(String(dest.id)));
  }

  function saveFullPlan() {
    if (!user) {
      navigate('/login');
      return;
    }
    const totalBudgetPkr =
      queryTotalBudget != null && queryTotalBudget > 0
        ? queryTotalBudget
        : dest.cost
          ? dest.cost * days
          : null;
    const perDay = totalBudgetPkr && days > 0 ? Math.round(totalBudgetPkr / days) : null;
    const autoHintLocal = [
      `Plan for ${days} day(s)`,
      totalBudgetPkr != null ? `total trip budget about ${totalBudgetPkr} PKR` : null,
      perDay != null ? `around ${perDay} PKR per day` : null,
    ]
      .filter(Boolean)
      .join('; ');
    const user_message = [planNotes.trim(), autoHintLocal].filter(Boolean).join('. ');
    setSaveStatus('Saving…');
    fetch(apiUrl('/api/trips/plan'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: user.id,
        destination_id: Number(dest.id) || dest.db_id,
        days,
        total_budget_pkr: totalBudgetPkr,
        user_message: user_message || undefined,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.itinerary) {
          setAiPlan({
            itinerary: data.itinerary,
            map_image_url: data.map_image_url,
            trip_meta: data.trip_meta,
            estimated_total_pkr: data.estimated_total_pkr,
            places_used: data.places_used_in_plan,
            planner: data.planner,
            weather_advisory: data.weather_advisory,
            weather_snapshot: data.weather_snapshot,
          });
        }
        const extra = data.planner === 'places_catalog_groq' ? ' (from places catalog)' : '';
        setSaveStatus(
          data.trip_id ? `Saved as trip #${data.trip_id}${extra}` : data.message || 'Done'
        );
      })
      .catch(() => setSaveStatus('Could not save'))
      .finally(() => {
        setTimeout(() => setSaveStatus(''), 4000);
      });
  }

  const displayPlan = aiPlan?.itinerary;
  const tripMeta = aiPlan?.trip_meta;
  const showDurationLine =
    tripMeta && typeof tripMeta.total_days === 'number'
      ? `${tripMeta.total_days} day${tripMeta.total_days === 1 ? '' : 's'} · ${
          tripMeta.hotel_nights
        } night${tripMeta.hotel_nights === 1 ? '' : 's'}`
      : `${days} day${days === 1 ? '' : 's'} · ${Math.max(0, days - 1)} night${
          Math.max(0, days - 1) === 1 ? '' : 's'
        }`;

  const perDayBudget =
    queryTotalBudget != null && days > 0
      ? Math.round(queryTotalBudget / days)
      : dest.cost || null;
  const estLine =
    aiPlan?.estimated_total_pkr != null && aiPlan.estimated_total_pkr > 0
      ? `${aiPlan.estimated_total_pkr.toLocaleString()} PKR (AI roll-up)`
      : null;

  const mapHref =
    dest.latitude && dest.longitude
      ? `https://www.openstreetmap.org/?mlat=${dest.latitude}&mlon=${dest.longitude}#map=12`
      : null;

  return (
    <div className="page page-trip plan-page">
      <div className="plan-hero">
        <div className="plan-hero-image" style={{ backgroundImage: `url(${image})` }} />
        <div className="plan-hero-text">
          <h1>{dest.name}</h1>
          <p className="plan-hero-sub muted">
            {dest.region} · {dest.type || dest.category}
            {mapHref && (
              <>
                {' '}
                ·{' '}
                <a href={mapHref} target="_blank" rel="noreferrer" className="plan-map-link">
                  Open area map
                </a>
              </>
            )}
          </p>
          <div className="plan-hero-actions">
            <button type="button" className={saved ? 'btn saved' : 'btn'} onClick={handleSave}>
              {saved ? 'Saved' : 'Save destination'}
            </button>
          </div>
        </div>
      </div>

      <div className="plan-grid">
        <main className="plan-main">
          {planError && <div className="plan-error-banner">{planError}</div>}

          {planLoading && !hasReceivedPlan && (
            <div className="plan-skeleton" aria-hidden>
              <div className="plan-skeleton-pills" />
              <div className="plan-skeleton-card" />
              <div className="plan-skeleton-card" />
              <p className="plan-loading-caption muted">Building your day-by-day plan…</p>
            </div>
          )}

          {planLoading && hasReceivedPlan && (
            <div className="plan-refreshing muted small">Updating itinerary…</div>
          )}

          {displayPlan && !planError && (
            <>
              <div className="plan-summary-pills">
                <span className="plan-pill plan-pill-strong">{showDurationLine}</span>
                {perDayBudget != null && (
                  <span className="plan-pill">~{perDayBudget.toLocaleString()} PKR / day (guide)</span>
                )}
                {estLine && <span className="plan-pill plan-pill-est">{estLine}</span>}
                {aiPlan?.places_used && (
                  <span className="plan-pill plan-pill-info">Real places from database</span>
                )}
              </div>

              {aiPlan?.weather_advisory && (
                <div
                  className={`plan-weather-advisory plan-weather--${
                    aiPlan.weather_advisory.severity || 'ok'
                  }`}
                >
                  <h4 className="plan-weather-title">Weather-aware AI</h4>
                  {aiPlan.weather_advisory.summary && (
                    <p className="plan-weather-summary">{aiPlan.weather_advisory.summary}</p>
                  )}
                  {aiPlan.weather_advisory.adjustments && (
                    <p className="plan-weather-adjust muted small">{aiPlan.weather_advisory.adjustments}</p>
                  )}
                  {aiPlan.weather_advisory.reschedule_suggestion && (
                    <p className="plan-weather-reschedule">
                      <strong>Rescheduling:</strong> {aiPlan.weather_advisory.reschedule_suggestion}
                    </p>
                  )}
                  {aiPlan.weather_snapshot && (
                    <p className="muted small plan-weather-snap">
                      Conditions used: {aiPlan.weather_snapshot.location || '—'} ·{' '}
                      {aiPlan.weather_snapshot.summary || '—'}
                      {aiPlan.weather_snapshot.temp_c != null && ` · ${aiPlan.weather_snapshot.temp_c}°C`}
                    </p>
                  )}
                </div>
              )}

              {tripMeta?.label && <p className="plan-label-line">{tripMeta.label}</p>}

              <div className="plan-day-list">
                {displayPlan.map((day) => (
                  <article key={day.day_number} className="plan-day-card">
                    <header className="plan-day-header">
                      <span className="plan-day-index">Day {day.day_number}</span>
                      {day.day_title && (
                        <h2 className="plan-day-title">{day.day_title}</h2>
                      )}
                    </header>
                    {day.day_summary && (
                      <p className="plan-day-summary">{day.day_summary}</p>
                    )}
                    <ul className="plan-blocks">
                      {(day.items || day.lines || []).map((line, i) => {
                        if (typeof line === 'string') {
                          return (
                            <li key={i} className="plan-block plan-block-simple">
                              {line}
                            </li>
                          );
                        }
                        const timeLine =
                          line.start_time && line.end_time
                            ? `${line.start_time} – ${line.end_time}`
                            : line.start_time || null;
                        const itype = (line.item_type || '').toLowerCase();
                        return (
                          <li key={i} className={`plan-block plan-block--${itype || 'other'}`}>
                            <div className="plan-block-top">
                              {timeLine && (
                                <span className="plan-block-time">{timeLine}</span>
                              )}
                              {itype && (
                                <span className="plan-block-badge">{itemTypeLabel(itype)}</span>
                              )}
                            </div>
                            <h3 className="plan-block-name">{line.title}</h3>
                            {line.description && (
                              <p className="plan-block-desc">{line.description}</p>
                            )}
                            <div className="plan-block-meta">
                              {line.place_address && (
                                <span className="plan-block-addr">{line.place_address}</span>
                              )}
                              {line.estimated_cost_pkr > 0 && (
                                <span className="plan-block-cost">
                                  ≈ {line.estimated_cost_pkr.toLocaleString()} PKR
                                </span>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </article>
                ))}
              </div>
            </>
          )}

        </main>

        <aside className="plan-side">
          <section className="plan-side-section">
            <h3>Adjust your trip</h3>
            <label className="plan-field">
              <span>Duration</span>
              <select
                className="plan-select"
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
              >
                {Array.from({ length: 14 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n} {n === 1 ? 'day' : 'days'}
                  </option>
                ))}
              </select>
            </label>
            {queryTotalBudget != null && days > 0 && (
              <p className="muted small plan-side-budget">
                From search: {queryTotalBudget.toLocaleString()} PKR total
              </p>
            )}
            <label className="plan-field">
              <span>Extra preferences (optional)</span>
              <textarea
                className="plan-textarea"
                rows={3}
                placeholder="e.g. local food, easy pace, one museum per day"
                value={planNotes}
                onChange={(e) => setPlanNotes(e.target.value)}
              />
            </label>
            <p className="muted small">
              The plan updates automatically when you change duration; notes apply after a short
              pause while typing.
            </p>
            <div className="plan-save-row">
              <button type="button" className="btn" onClick={saveFullPlan}>
                Save to my trips
              </button>
              {saveStatus && <span className="muted small plan-save-status">{saveStatus}</span>}
            </div>
            <p className="muted small">
              Save stores this itinerary in your account. The preview does not require login.
            </p>
          </section>

          <section className="plan-side-section">
            <h3>About {dest.name}</h3>
            <p className="plan-about muted">{dest.summary || dest.description || '—'}</p>
          </section>

          <section className="plan-side-section">
            <h3>Cost hint</h3>
            {aiPlan?.estimated_total_pkr != null && aiPlan.estimated_total_pkr > 0 && (
              <p className="plan-side-est">
                AI line items total:{' '}
                <strong>{aiPlan.estimated_total_pkr.toLocaleString()} PKR</strong> (indicative)
              </p>
            )}
            <CostSummary dest={dest} duration={days} />
          </section>

          <section className="plan-side-section">
            <h3>Current weather</h3>
            {liveWeather && liveWeather.temp_c != null && (
              <p className="plan-about" style={{ margin: '0 0 4px' }}>
                <strong>
                  {liveWeather.summary || '—'}
                  {` · ${liveWeather.temp_c}°C`}
                </strong>
                {liveWeather.feels_c != null && liveWeather.feels_c !== liveWeather.temp_c && (
                  <span className="muted small"> (feels {liveWeather.feels_c}°C)</span>
                )}
              </p>
            )}
            {liveWeather && liveWeather.location && (
              <p className="muted small" style={{ margin: '0 0 4px' }}>
                Location: {liveWeather.location} · humidity {liveWeather.humidity ?? '—'}
                {liveWeather.wind_m_s != null ? ` · wind ${liveWeather.wind_m_s} m/s` : ''}
              </p>
            )}
            {liveWeatherNote && <p className="muted small">{liveWeatherNote}</p>}
            <p className="muted small" style={{ marginTop: 6 }}>
              Powered by Open Weather 13 (RapidAPI), same key as the home page.
            </p>
          </section>

          <section className="plan-side-section plan-side-meta">
            <div className="muted small">Best season: {dest.best_season || '—'}</div>
            <div className="muted small">Climate: {dest.weather || dest.climate || '—'}</div>
            <div className="muted small">Rating: {dest.user_rating ?? '—'}</div>
          </section>
        </aside>
      </div>
    </div>
  );
}
