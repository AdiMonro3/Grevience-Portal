import { Navigate, Outlet, useLocation } from "react-router";
import { homePathFor, useAuth } from "../auth/AuthContext";
import { PageLoader } from "./States";

/** Wrap routes that need login; `roles` limits them to some roles. */
export default function ProtectedRoute({ roles, children }) {
  const { user, loading, signedOut } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader />;
  if (!user) {
    // Remember the page so login can return to it, unless the user just clicked Logout
    const state = signedOut ? undefined : { from: location.pathname + location.search };
    return <Navigate to="/login" replace state={state} />;
  }
  if (roles && !roles.includes(user.role)) return <Navigate to={homePathFor(user)} replace />;
  return children ?? <Outlet />;
}
