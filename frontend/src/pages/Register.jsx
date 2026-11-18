import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { errorMessage } from "../api/client";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { ErrorBox, Spinner } from "../components/States";

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePathFor(user)} replace />;

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register({ ...form, phone: form.phone || null });
      navigate("/location", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-6 max-w-md">
      <div className="card space-y-4 p-6">
        <div>
          <h1 className="text-2xl font-bold">Create account</h1>
          <p className="text-sm text-slate-500">Updates on your complaints are sent to this email.</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="name">Full name</label>
            <input id="name" className="input" value={form.name} onChange={set("name")} required minLength={2} />
          </div>
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={form.email} onChange={set("email")} required />
          </div>
          <div>
            <label className="label" htmlFor="phone">Phone (optional)</label>
            <input id="phone" type="tel" className="input" value={form.phone} onChange={set("phone")} maxLength={20} />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" className="input" value={form.password} onChange={set("password")} required minLength={6} autoComplete="new-password" />
            <p className="mt-1 text-xs text-slate-500">At least 6 characters.</p>
          </div>
          <ErrorBox message={error} />
          <button className="btn btn-primary w-full" disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Create account
          </button>
        </form>
        <p className="text-center text-sm text-slate-600">
          Already registered?{" "}
          <Link to="/login" className="font-medium text-blue-700 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
