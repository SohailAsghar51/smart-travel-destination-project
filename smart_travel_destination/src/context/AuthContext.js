// Login state for the whole app (user, profile, saved trips). Any page can read it with useAuth().
import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiUrl } from '../api/client';

const AuthContext = createContext(null);

const SESSION_KEY = 'st_session';

function readSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    const s = readSession();
    if (s && s.user) {
      setUser({ ...s.user, role: s.user.role || 'user' });
      setProfile(s.profile || null);
    }
  }, []);

  useEffect(() => {
    if (!user || !user.id) return undefined;
    let cancelled = false;
    fetch(apiUrl(`/api/favorites/${user.id}`))
      .then((r) => r.json())
      .then((data) => {
        if (cancelled || !data.favorites) return;
        const ids = data.favorites.map((d) => String(d.id));
        setUser((u) => (u ? { ...u, saved: ids } : u));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- only refetch when user id changes
  }, [user?.id]);

  function persist(userObj, prof) {
    const p = prof || userObj.profile;
    const merged = { ...userObj, profile: p };
    localStorage.setItem(SESSION_KEY, JSON.stringify({ user: merged, profile: p }));
    setProfile(p || null);
    setUser(merged);
  }

  async function register({ email, name, password }) {
    const res = await fetch(apiUrl('/api/register'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || 'Registration failed');
    }
    const u = {
      id: data.user.id,
      name: data.user.full_name || data.user.name,
      email: data.user.email,
      full_name: data.user.full_name,
      saved: [],
      role: data.user.role || 'user',
    };
    persist(u, data.profile);
    return u;
  }

  function login(sessionUser, prof) {
    const u = {
      id: sessionUser.id,
      name: sessionUser.name,
      email: sessionUser.email,
      full_name: sessionUser.name,
      saved: sessionUser.saved || [],
      role: sessionUser.role || 'user',
    };
    persist(u, prof);
  }

  function logout() {
    localStorage.removeItem(SESSION_KEY);
    setUser(null);
    setProfile(null);
  }

  async function updateProfile(patch) {
    if (!user || !user.id) return;
    const body = {
      budget: patch.budget,
      styles: patch.styles,
      duration: patch.duration,
      typical_trip_duration_days: patch.duration,
    };
    const res = await fetch(apiUrl(`/api/profile/${user.id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || 'Update failed');
    }
    const prof = data.profile;
    setProfile(prof);
    setUser((prev) => {
      if (!prev) return prev;
      const next = { ...prev, profile: prof };
      localStorage.setItem(SESSION_KEY, JSON.stringify({ user: next, profile: prof }));
      return next;
    });
    return prof;
  }

  async function toggleSaveTrip(destId) {
    if (!user || !user.id) {
      return null;
    }
    const res = await fetch(apiUrl('/api/favorites'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: user.id,
        destination_id: destId,
      }),
    });
    const data = await res.json();
    const idStr = String(destId);
    const list = [...(user.saved || [])];
    if (data.saved) {
      if (!list.includes(idStr)) list.push(idStr);
    } else {
      const idx = list.indexOf(idStr);
      if (idx !== -1) list.splice(idx, 1);
    }
    const next = { ...user, saved: list };
    const s = readSession();
    const prof = s && s.profile ? s.profile : user.profile;
    localStorage.setItem(SESSION_KEY, JSON.stringify({ user: next, profile: prof }));
    setUser(next);
    return list;
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        profile: profile || user?.profile,
        register,
        login,
        logout,
        updateProfile,
        toggleSaveTrip,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export default AuthContext;
