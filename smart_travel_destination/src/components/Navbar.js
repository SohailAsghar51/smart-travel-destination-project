import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  return (
    <nav className="site-nav">
      <div className="nav-inner">
        <div className="brand">SmartTravel</div>
        <div className="nav-links">
          <NavLink to="/" className={({isActive}) => isActive ? 'active' : ''} >Discover</NavLink>
          <NavLink to="/explore" className={({isActive}) => isActive ? 'active' : ''}>Explore</NavLink>
          <NavLink to="/trips" className={({isActive}) => isActive ? 'active' : ''}>Saved Trips</NavLink>
          <NavLink to="/about" className={({isActive}) => isActive ? 'active' : ''}>About</NavLink>
          {user && user.role === 'admin' && (
            <NavLink to="/admin" className={({isActive}) => isActive ? 'active' : ''}>Admin</NavLink>
          )}
        </div>
        <div className="nav-actions">
          {user ? (
            <>
              <button className="btn small" onClick={() => nav('/profile')}>{user.name}</button>
              <button className="btn-outline small" onClick={() => { logout(); nav('/'); }}>Sign out</button>
            </>
          ) : (
            <>
              <button className="btn small" onClick={() => nav('/login')}>Sign in</button>
              <button className="btn-outline small" onClick={() => nav('/register')}>Register</button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
