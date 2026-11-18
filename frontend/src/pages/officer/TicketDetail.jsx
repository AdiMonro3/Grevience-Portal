import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import ComplaintView from "../../components/ComplaintView";
import MediaUpload from "../../components/MediaUpload";
import Modal from "../../components/Modal";
import { ErrorBox, Notice, PageLoader, Spinner } from "../../components/States";

function ResolveDialog({ ticketNo, onClose, onDone }) {
  const [note, setNote] = useState("");
  const [photos, setPhotos] = useState([]);
  const [video, setVideo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    const form = new FormData();
    if (note.trim()) form.append("note", note.trim());
    photos.forEach((p) => form.append("photos", p));
    if (video) form.append("video", video);
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/officer/complaints/${ticketNo}/resolve`, form);
      onDone(data, "Marked as resolved. The citizen has been emailed.");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Resolve complaint" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="note">What was done?</label>
          <textarea id="note" className="input min-h-24" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder="e.g. Pothole filled and road levelled" />
        </div>
        <div>
          <span className="label">Proof photo / video (recommended)</span>
          <MediaUpload photos={photos} onPhotosChange={setPhotos} video={video} onVideoChange={setVideo} />
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-success" disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Mark resolved
          </button>
        </div>
      </form>
    </Modal>
  );
}

function RejectDialog({ ticketNo, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.patch(`/officer/complaints/${ticketNo}/status`, { status: "REJECTED", reason: reason.trim() });
      onDone(data, "Complaint rejected. The citizen has been emailed the reason.");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Reject complaint" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="reason">Reason (sent to the citizen)</label>
          <textarea id="reason" className="input min-h-24" value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} maxLength={1000} placeholder="e.g. Private property, not under municipal jurisdiction" />
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-danger" disabled={busy || reason.trim().length < 3}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Reject
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default function TicketDetail() {
  const { ticketNo } = useParams();
  const { user } = useAuth();
  const [c, setC] = useState(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState(null); // "resolve" | "reject"

  const load = useCallback(() => {
    setError("");
    api
      .get(`/officer/complaints/${ticketNo}`)
      .then((r) => setC(r.data))
      .catch((err) => setError(errorMessage(err)));
  }, [ticketNo]);

  useEffect(load, [load]);

  function done(updated, msg) {
    setC(updated);
    setDialog(null);
    setMessage(msg);
    setActionError("");
  }

  async function run(request, msg) {
    setBusy(true);
    setActionError("");
    setMessage("");
    try {
      const { data } = await request();
      done(data, msg);
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const pickUp = () =>
    run(() => api.post(`/officer/complaints/${ticketNo}/pick`), "Ticket picked up. The citizen has been emailed your name and contact.");
  const startWork = () =>
    run(
      () => api.patch(`/officer/complaints/${ticketNo}/status`, { status: "IN_PROGRESS", reason: "Work started" }),
      "Marked in progress. The citizen has been emailed.",
    );

  let actions = null;
  if (c) {
    const mine = c.assigned_officer?.email === user.email;
    const buttons = [];
    if (c.status === "OPEN") {
      buttons.push(
        <button key="pick" className="btn btn-primary" onClick={pickUp} disabled={busy}>
          {busy && <Spinner className="h-4 w-4 text-white" />} 🙋 Pick up this ticket
        </button>,
      );
    }
    if (mine && c.status === "ASSIGNED") {
      buttons.push(
        <button key="start" className="btn btn-primary" onClick={startWork} disabled={busy}>
          {busy && <Spinner className="h-4 w-4 text-white" />} 🛠 Mark in progress
        </button>,
      );
    }
    if (mine && ["ASSIGNED", "IN_PROGRESS"].includes(c.status)) {
      buttons.push(
        <button key="resolve" className="btn btn-success" onClick={() => setDialog("resolve")} disabled={busy}>
          ✓ Resolve
        </button>,
        <button key="reject" className="btn btn-secondary text-red-700" onClick={() => setDialog("reject")} disabled={busy}>
          Reject
        </button>,
      );
    }
    actions = (
      <div className="space-y-2">
        {message && <Notice tone="success">{message}</Notice>}
        <ErrorBox message={actionError} />
        {buttons.length > 0 && <div className="card flex flex-wrap items-center gap-2">{buttons}</div>}
        {!mine && c.assigned_officer && !["RESOLVED", "REJECTED"].includes(c.status) && (
          <Notice>Assigned to {c.assigned_officer.name}.</Notice>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/officer" className="text-sm text-blue-700 hover:underline">
          ← Back to queue
        </Link>
        {c && (
          <button onClick={load} className="btn btn-secondary btn-sm">
            ↻ Refresh
          </button>
        )}
      </div>
      <ErrorBox message={error} onRetry={load} />
      {!c && !error && <PageLoader />}
      {c && <ComplaintView complaint={c} staff actions={actions} />}
      {dialog === "resolve" && <ResolveDialog ticketNo={ticketNo} onClose={() => setDialog(null)} onDone={done} />}
      {dialog === "reject" && <RejectDialog ticketNo={ticketNo} onClose={() => setDialog(null)} onDone={done} />}
    </div>
  );
}
