// First file that runs in the browser. It mounts (shows) the main App inside the HTML page.
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Optional: measure page speed (you can delete this line in a school project)
reportWebVitals();
