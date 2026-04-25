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
 * One full API URL. We always use a "/" before "?" in the path (style: /api/home/ not /api/home).
 * path: like "/api/home" or "/api/trips" — you can skip or keep the final "/"; we add it if missing.
 * For "?query=1", do: \`\${apiUrl('/api/weather')}?lat=...\`  (the "?" part comes after the trailing slash)
 */
export function apiUrl(path) {
  const base = getApiBase();
  let p = path.startsWith('/') ? path : `/${path}`;
  if (!p.endsWith('/')) p += '/';
  return `${base}${p}`;
}
