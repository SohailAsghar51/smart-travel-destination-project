import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiBase } from '../api/client';

export default function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState(null);
  const auth = useAuth();
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError(null);

    try {
      const res = await fetch(`${getApiBase()}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(form),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.message || 'Login failed');
      }

      auth.login(
        {
          id: data.data.id,
          name: data.data.name,
          email: data.data.email,
          saved: [],
        },
        data.profile
      );
      navigate('/profile');
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <div className="page page-auth">
      <h1>Sign in</h1>
      <form className="auth-form" onSubmit={submit}>
        <label>Email</label>
        <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <label>Password</label>
        <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <div className="error">{error}</div>}
        <div style={{ marginTop: 8 }}>
          <button className="btn" type="submit">
            Sign in
          </button>
        </div>
      </form>
    </div>
  );
}
