import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";

const LINKS = {
  citizen: [
    { to: "/nearby", label: "Nearby" },
    { to: "/complaints/new", label: "Report issue" },
    { to: "/complaints", label: "My complaints", end: true },
    { to: "/location", label: "My location" },
  ],
  officer: [{ to: "/officer", label: "My queue", end: true }],
  admin: [{ to: "/admin/triage", label: "Triage" }],
};

function navCls({ isActive }) {
  return `rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? "bg-blue-800 text-white" : "text-blue-100 hover:bg-blue-600 hover:text-white"
  }`;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const links = user ? LINKS[user.role] || [] : [];

  function handleLogout() {
    logout(); // marks the logout as deliberate, so ProtectedRoute won't remember this page
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen">
      <header className="bg-blue-700 text-white shadow">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold">
            <img src="/favicon.svg" alt="" className="h-7 w-7 rounded-md ring-2 ring-white/40" />
            Grievance Portal
          </Link>

          {user && (
            <>
              <nav className="hidden items-center gap-1 md:flex">
                {links.map((l) => (
                  <NavLink key={l.to} to={l.to} end={l.end} className={navCls}>
                    {l.label}
                  </NavLink>
                ))}
              </nav>
              <div className="hidden items-center gap-3 md:flex">
                <div className="text-right text-xs leading-tight">
                  <div className="font-semibold">{user.name}</div>
                  <div className="text-blue-200 capitalize">
                    {user.role}
                    {user.role === "officer" && user.department && ` · ${user.department.name} · ${user.ward?.code}`}
                  </div>
                </div>
                <button onClick={handleLogout} className="rounded-md bg-blue-800 px-3 py-1.5 text-sm hover:bg-blue-900">
                  Logout
                </button>
              </div>
              <button className="rounded-md p-2 hover:bg-blue-600 md:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
                ☰
              </button>
            </>
          )}
        </div>

        {user && open && (
          <div className="border-t border-blue-600 px-4 pt-2 pb-3 md:hidden" onClick={() => setOpen(false)}>
            <div className="mb-2 text-xs text-blue-200">
              {user.name} · <span className="capitalize">{user.role}</span>
            </div>
            <nav className="flex flex-col gap-1">
              {links.map((l) => (
                <NavLink key={l.to} to={l.to} end={l.end} className={navCls}>
                  {l.label}
                </NavLink>
              ))}
              <button onClick={handleLogout} className="rounded-md px-3 py-2 text-left text-sm text-blue-100 hover:bg-blue-600">
                Logout
              </button>
            </nav>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
