import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import StatusBadge from "../../components/StatusBadge";
import { ErrorBox, Notice, PageLoader } from "../../components/States";

function Row({ label, children }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-100 py-2 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  );
}

export default function Submitted() {
  const { ticketNo } = useParams();
  const location = useLocation();
  const [c, setC] = useState(location.state?.complaint || null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (c) return;
    api
      .get(`/complaints/${ticketNo}`)
      .then((r) => setC(r.data))
      .catch((err) => setError(errorMessage(err)));
  }, [c, ticketNo]);

  if (error) return <ErrorBox message={error} />;
  if (!c) return <PageLoader />;

  const triage = c.status === "TRIAGE";
  const triageNote = c.history.find((h) => h.note?.startsWith("Sent to manual triage"))?.note;

  async function copy() {
    try {
      await navigator.clipboard.writeText(c.ticket_no);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the number is on screen anyway */
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <div className="card space-y-4 p-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-3xl">✓</div>
        <div>
          <h1 className="text-xl font-bold">Complaint submitted</h1>
          <p className="text-sm text-slate-500">We've emailed you a copy. Keep this ticket number to track it.</p>
        </div>
        <button onClick={copy} className="mx-auto block rounded-lg bg-slate-100 px-4 py-2 font-mono text-2xl font-bold tracking-wide hover:bg-slate-200" title="Copy">
          {c.ticket_no}
        </button>
        <p className="h-4 text-xs text-green-700">{copied && "Copied!"}</p>
      </div>

      <div className="card">
        <Row label="Status">
          <StatusBadge status={c.status} />
        </Row>
        <Row label="Detected category">
          {c.category?.name || c.predicted_category?.name || "—"}
          {c.ml_confidence != null && (
            <span className="ml-1 text-xs font-normal text-slate-500">({Math.round(c.ml_confidence * 100)}% sure)</span>
          )}
        </Row>
        <Row label="Department">{c.department?.name || "Being reviewed"}</Row>
        <Row label="Ward">{c.ward?.name || "Being reviewed"}</Row>
      </div>

      {triage && (
        <Notice tone="warning">
          We couldn't route this automatically{triageNote ? ` (${triageNote.replace("Sent to manual triage: ", "")})` : ""}. An
          admin will check it and send it to the right department. You'll get an email when that happens.
        </Notice>
      )}

      <div className="flex flex-wrap gap-2">
        <Link to={`/complaints/${c.ticket_no}`} className="btn btn-primary flex-1">
          View complaint
        </Link>
        <Link to="/complaints" className="btn btn-secondary flex-1">
          My complaints
        </Link>
        <Link to="/nearby" className="btn btn-secondary flex-1">
          Back to nearby
        </Link>
      </div>
    </div>
  );
}
