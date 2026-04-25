import React from 'react';
import './App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import RegisterPage from './pages/RegisterPage';
import LoginPage from './pages/LoginPage';
import ProfilePage from './pages/ProfilePage';
import TripDetails from './pages/TripDetails';
import HomePage from './pages/HomePage';
import ExplorePage from './pages/ExplorePage';
import TripsPage from './pages/TripsPage';
import SavedTripPage from './pages/SavedTripPage';
import AboutPage from './pages/AboutPage';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="App site-root">
          <Navbar />
          <main className="App-container">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/explore" element={<ExplorePage />} />
              <Route path="/trips" element={<TripsPage />} />
              <Route path="/trips/saved/:tripId" element={<SavedTripPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/trip/:id" element={<TripDetails />} />
            </Routes>
          </main>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
