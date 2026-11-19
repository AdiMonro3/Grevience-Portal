import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import ComplaintView from "../../components/ComplaintView";
import Modal from "../../components/Modal";
import { ErrorBox, Notice, PageLoader, Spinner } from "../../components/States";

function ReopenDialog({ ticketNo, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/complaints/${ticketNo}/reopen`, { reason: reason.trim() });
      onDone(data);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Reopen complaint" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Tell the officer what is still wrong. The complaint goes back to them with a higher priority.
        </p>
        <div>
          <label className="label" htmlFor="reason">What is still wrong?</label>
          <textarea
            id="reason"
            className="input min-h-24"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            minLength={5}
            maxLength={500}
            placeholder="e.g. The drain is blocked again and dirty water is still coming into the house"
          />
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy || reason.trim().length < 5}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Reopen
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default function ComplaintDetail() {
  const { ticketNo } = useParams();
  const { user } = useAuth();
  const [c, setC] = useState(null);
  const [error, setError] = useState("");
  const [reopening, setReopening] = useState(false);
  const [message, setMessage] = useState("");

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

  function reopened(updated) {
    setC(updated);
    setReopening(false);
    setMessage(
      updated.assigned_officer
        ? `Complaint reopened. It is back with ${updated.assigned_officer.name}, who has been emailed.`
        : "Complaint reopened. It is back in the department's queue.",
    );
  }

  const canReopen = user.role === "citizen" && c?.can_reopen;
  const actions =
    message || canReopen ? (
      <div className="space-y-2">
        {message && <Notice tone="success">{message}</Notice>}
        {canReopen && (
          <div className="card flex flex-wrap items-center justify-between gap-3 border-amber-200 bg-amber-50">
            <p className="text-sm text-amber-900">
              <b>Problem not fixed?</b> Reopen the complaint and it goes back to the officer.
            </p>
            <button className="btn btn-secondary" onClick={() => setReopening(true)}>
              ↺ Reopen complaint
            </button>
          </div>
        )}
      </div>
    ) : null;

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
      {c && <ComplaintView complaint={c} staff={user.role === "admin"} actions={actions} />}
      {reopening && <ReopenDialog ticketNo={ticketNo} onClose={() => setReopening(false)} onDone={reopened} />}
    </div>
  );
}
