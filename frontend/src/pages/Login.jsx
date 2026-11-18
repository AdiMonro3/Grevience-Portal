import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { errorMessage } from "../api/client";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { ErrorBox, Spinner } from "../components/States";

const DEMO_ACCOUNTS = [
  { label: "Citizen", email: "citizen1@gp.demo" },
  { label: "Officer · Sewer W4", email: "sewer.w4@gp.demo" },
  { label: "Officer · Roads W4", email: "roads.w4@gp.demo" },
  { label: "Admin", email: "admin@gp.demo" },
];

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePathFor(user)} replace />;

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await login(email, password);
      // Back to the page that asked for login; ProtectedRoute bounces wrong roles home
      navigate(location.state?.from || homePathFor(u), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-6 max-w-md space-y-4">
      <div className="card space-y-4 p-6">
        <div>
          <h1 className="text-2xl font-bold">Log in</h1>
          <p className="text-sm text-slate-500">Report civic issues and track them till they're fixed.</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          </div>
          <ErrorBox message={error} />
          <button className="btn btn-primary w-full" disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Log in
          </button>
        </form>
        <p className="text-center text-sm text-slate-600">
          New here?{" "}
          <Link to="/register" className="font-medium text-blue-700 hover:underline">
            Create a citizen account
          </Link>
        </p>
      </div>

      <div className="card text-sm">
        <p className="mb-2 font-medium text-slate-700">Demo accounts (password Demo@123)</p>
        <div className="flex flex-wrap gap-2">
          {DEMO_ACCOUNTS.map((a) => (
            <button
              key={a.email}
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setEmail(a.email);
                setPassword("Demo@123");
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
