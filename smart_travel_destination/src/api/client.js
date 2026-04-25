// Base URL for the Flask API (Create React App reads REACT_APP_* at build time)
export function getApiBase() {
  return process.env.REACT_APP_API_URL || 'http://127.0.0.1:5000';
}
