// How we talk to the Python (Flask) server from React.
// Create React App only reads REACT_APP_* from .env at build time (restart npm after change).

/**
 * The server address only (no path). Example: http://127.0.0.1:5000
 * We remove extra "/" at the end so paths join cleanly.
 */
export function getApiBase() {
  const raw = process.env.REACT_APP_API_URL || 'http://127.0.0.1:5000';
  return String(raw).replace(/\/+$/, '');
}

/**
 * One full API URL. For paths without a query, we add a trailing "/" (to match the Flask app).
 * If the path already contains "?", we do not add "/" (or it would break ?limit=500 into limit=500/).
 * For query args, you can also do: \`\${apiUrl('/api/weather')}?lat=...\`
 */
export function apiUrl(path) {
  const base = getApiBase();
  let p = path.startsWith('/') ? path : `/${path}`;
  if (p.includes('?')) {
    return `${base}${p}`;
  }
  if (!p.endsWith('/')) p += '/';
  return `${base}${p}`;
}
