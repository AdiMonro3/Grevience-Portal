import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import ComplaintView from "../../components/ComplaintView";
import { ErrorBox, PageLoader } from "../../components/States";

export default function ComplaintDetail() {
  const { ticketNo } = useParams();
  const { user } = useAuth();
  const [c, setC] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    api
      .get(`/complaints/${ticketNo}`)
      .then((r) => setC(r.data))
      .catch((err) => setError(errorMessage(err)));
  }, [ticketNo]);

  useEffect(() => {
    if (user.role !== "officer") load();
  }, [load, user.role]);

  // Officers have their own page with the action buttons
  if (user.role === "officer") return <Navigate to={`/officer/tickets/${ticketNo}`} replace />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link to={user.role === "admin" ? "/admin/triage" : "/complaints"} className="text-sm text-blue-700 hover:underline">
          ← Back
        </Link>
        {c && (
          <button onClick={load} className="btn btn-secondary btn-sm">
            ↻ Refresh
          </button>
        )}
      </div>
      <ErrorBox message={error} onRetry={load} />
      {!c && !error && <PageLoader />}
      {c && <ComplaintView complaint={c} staff={user.role === "admin"} />}
    </div>
  );
}
