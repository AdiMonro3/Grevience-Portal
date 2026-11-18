import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, errorMessage, mediaUrl } from "../../api/client";
import { EmptyState, ErrorBox, Notice, PageLoader, Spinner } from "../../components/States";
import { formatDateTime, timeAgo } from "../../lib/format";

function TriageCard({ c, departments, wards, categories, onDone }) {
  const suggested = categories.find((x) => x.id === c.predicted_category?.id);
  const [deptId, setDeptId] = useState(c.department?.id ?? suggested?.department.id ?? "");
  const [wardId, setWardId] = useState(c.ward?.id ?? "");
  const [catId, setCatId] = useState(() => {
    const dept = c.department?.id ?? suggested?.department.id;
    return suggested && suggested.department.id === dept ? suggested.id : "";
  });
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const deptCategories = categories.filter((x) => x.department.id === Number(deptId));
  const triageNote = [...c.history].reverse().find((h) => h.note?.startsWith("Sent to manual triage"))?.note;
  const photos = c.media.filter((m) => m.kind === "photo");

  function changeDept(value) {
    setDeptId(value);
    if (!categories.some((x) => x.id === Number(catId) && x.department.id === Number(value))) setCatId("");
  }

  async function act(request, msg) {
    setBusy(true);
    setError("");
    try {
      await request();
      onDone(c.ticket_no, msg);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const route = () =>
    act(
      () =>
        api.patch(`/admin/complaints/${c.ticket_no}/assign`, {
          department_id: Number(deptId),
          ward_id: Number(wardId),
          category_id: catId ? Number(catId) : null,
        }),
      `${c.ticket_no} routed. The citizen has been emailed.`,
    );
  const reject = () =>
    act(() => api.post(`/admin/complaints/${c.ticket_no}/reject`, { reason: reason.trim() }), `${c.ticket_no} rejected.`);

  return (
    <li className="card space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <Link to={`/complaints/${c.ticket_no}`} className="font-mono text-sm font-semibold text-blue-700 hover:underline">
            {c.ticket_no}
          </Link>
          <span className="ml-2 text-xs text-slate-500" title={formatDateTime(c.created_at)}>
            {timeAgo(c.created_at)} · by {c.citizen?.name}
          </span>
        </div>
        {triageNote && <span className="badge bg-amber-100 text-amber-800">{triageNote.replace("Sent to manual triage: ", "")}</span>}
      </div>

      <div className="flex gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm whitespace-pre-wrap">{c.description}</p>
          <p className="text-xs text-slate-500">
            📍 {c.address || "No address"}
            {c.lat != null && (
              <>
                {" "}·{" "}
                <a className="text-blue-700 hover:underline" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${c.lat}&mlon=${c.lng}#map=16/${c.lat}/${c.lng}`}>
                  map
                </a>
              </>
            )}
            {" "}· {c.ward ? c.ward.name : <span className="text-amber-700">outside all wards</span>}
          </p>
          <p className="text-xs text-slate-500">
            🤖 Model suggests <b>{c.predicted_category?.name || "—"}</b>
            {c.ml_confidence != null && ` (${Math.round(c.ml_confidence * 100)}%)`} · severity {c.severity}
          </p>
        </div>
        {photos.length > 0 && (
          <div className="flex flex-none gap-1">
            {photos.slice(0, 2).map((m) => (
              <a key={m.id} href={mediaUrl(m.url)} target="_blank" rel="noreferrer">
                <img src={mediaUrl(m.url)} alt="" className="h-16 w-16 rounded object-cover" />
              </a>
            ))}
          </div>
        )}
      </div>

      {!rejecting ? (
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto_auto]">
          <select className="input" value={deptId} onChange={(e) => changeDept(e.target.value)} aria-label="Department">
            <option value="">Department…</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          <select className="input" value={catId} onChange={(e) => setCatId(e.target.value)} disabled={!deptId} aria-label="Category">
            <option value="">Category (optional)…</option>
            {deptCategories.map((x) => (
              <option key={x.id} value={x.id}>{x.name}</option>
            ))}
          </select>
          <select className="input" value={wardId} onChange={(e) => setWardId(e.target.value)} aria-label="Ward">
            <option value="">Ward…</option>
            {wards.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={route} disabled={busy || !deptId || !wardId}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Route
          </button>
          <button className="btn btn-secondary text-red-700" onClick={() => setRejecting(true)} disabled={busy}>
            Reject
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <input className="input flex-1" placeholder="Reason, e.g. spam / duplicate of GRV-26-00012" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
          <button className="btn btn-danger" onClick={reject} disabled={busy || reason.trim().length < 3}>
            Confirm reject
          </button>
          <button className="btn btn-secondary" onClick={() => setRejecting(false)}>
            Cancel
          </button>
        </div>
      )}
      <ErrorBox message={error} />
    </li>
  );
}

export default function Triage() {
  const [items, setItems] = useState(null);
  const [ref, setRef] = useState({ departments: [], wards: [], categories: [] });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [triage, departments, wards, categories] = await Promise.all([
        api.get("/admin/triage"),
        api.get("/departments"),
        api.get("/wards"),
        api.get("/categories"),
      ]);
      setRef({ departments: departments.data, wards: wards.data, categories: categories.data });
      setItems(triage.data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function done(ticketNo, msg) {
    setItems((list) => list.filter((c) => c.ticket_no !== ticketNo));
    setMessage(msg);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Triage</h1>
          <p className="text-sm text-slate-500">
            Complaints the model wasn't sure about, or outside every ward. Route them by hand.
          </p>
        </div>
        <button onClick={load} className="btn btn-secondary btn-sm">
          ↻ Refresh
        </button>
      </div>
      {message && <Notice tone="success">{message}</Notice>}
      <ErrorBox message={error} onRetry={load} />
      {items === null && !error && <PageLoader />}
      {items?.length === 0 && <EmptyState title="Triage is empty 🎉">Every complaint has been routed.</EmptyState>}
      <ul className="space-y-3">
        {items?.map((c) => (
          <TriageCard key={c.ticket_no} c={c} {...ref} onDone={done} />
        ))}
      </ul>
    </div>
  );
}
