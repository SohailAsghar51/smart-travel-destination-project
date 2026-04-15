import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function RegisterPage() {
  const [form, setForm] = useState({ email: '', name: '', password: '' });
  const [error, setError] = useState(null);
  const auth = useAuth();
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError(null);
    try {
      auth.register(form);
      navigate('/profile');
    } catch (err) {
      setError(err.message || String(err));
    }
  }

  return (
    <div className="page page-auth">
      <h1>Create account</h1>
      <form className="auth-form" onSubmit={submit}>
        <label>Email</label>
        <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <label>Password</label>
        <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <div className="error">{error}</div>}
        <div style={{ marginTop: 8 }}>
          <button className="btn" type="submit">Register</button>
        </div>
      </form>
    </div>
  );
}
