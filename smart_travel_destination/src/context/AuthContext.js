import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

const USERS_KEY = 'st_users';
const CURRENT_KEY = 'st_current_user';

function readUsers() {
  try { return JSON.parse(localStorage.getItem(USERS_KEY) || '[]'); } catch { return []; }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    try {
      const raw_string = localStorage.getItem(CURRENT_KEY);
      if (raw_string) setUser(JSON.parse(raw_string));
    } catch (e) {
      alert(e)
    }
  }, []);

  function register({ email, name, password }) {
    const users = readUsers();
    if (users.find((u) => u.email === email)) {
      throw new Error('User already exists');
    }
    const newUser = { email, name, password, profile: { budget: 25000, styles: [], duration: 3 } };
    users.push(newUser);
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
    localStorage.setItem(CURRENT_KEY, JSON.stringify(newUser));
    setUser(newUser);
    return newUser;
  }

  function login(user) {
    setUser(user);
    localStorage.setItem(CURRENT_KEY,JSON.stringify(user));
    return user;
  }

  function logout() {
    localStorage.removeItem(CURRENT_KEY);
    setUser(null);
  }

  function updateProfile(patch) {
    const users = readUsers();
    if (!user) return;
    const idx = users.findIndex((u) => u.email === user.email);
    const updated = { ...users[idx], profile: { ...(users[idx].profile || {}), ...patch } };
    users[idx] = updated;
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
    localStorage.setItem(CURRENT_KEY, JSON.stringify(updated));
    setUser(updated);
    return updated;
  }

  function toggleSaveTrip(id) {
    // If no logged-in user, store in guest_saved
    if (!user) {
      try {
        const raw = JSON.parse(localStorage.getItem('guest_saved') || '[]');
        const idx = raw.indexOf(id);
        if (idx === -1) raw.push(id); else raw.splice(idx, 1);
        localStorage.setItem('guest_saved', JSON.stringify(raw));
        return raw;
      } catch (e) {
        return [];
      }
    }

    const users = readUsers();
    const idx = users.findIndex((u) => u.email === user.email);
    if (idx === -1) return;
    const saved = users[idx].saved || [];
    const found = saved.includes(id);
    const next = found ? saved.filter((x) => x !== id) : [...saved, id];
    users[idx] = { ...users[idx], saved: next };
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
    const updated = { ...users[idx] };
    localStorage.setItem(CURRENT_KEY, JSON.stringify(updated));
    setUser(updated);
    return next;
  }

  return (
    <AuthContext.Provider value={{ user, register, login, logout, updateProfile, toggleSaveTrip }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export default AuthContext;
