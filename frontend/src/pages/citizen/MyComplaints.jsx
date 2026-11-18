import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, errorMessage, mediaUrl } from "../../api/client";
import StatusBadge from "../../components/StatusBadge";
import { EmptyState, ErrorBox, PageLoader } from "../../components/States";
import { ACTIVE_STATUSES, timeAgo } from "../../lib/format";

const TABS = [
  { key: "all", label: "All", match: () => true },
  { key: "active", label: "Active", match: (c) => ACTIVE_STATUSES.includes(c.status) },
  { key: "closed", label: "Closed", match: (c) => !ACTIVE_STATUSES.includes(c.status) },
];

export default function MyComplaints() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");

  const load = useCallback(() => {
    setError("");
    api
      .get("/complaints/mine")
      .then((r) => setItems(r.data))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(load, [load]);

  const shown = items?.filter(TABS.find((t) => t.key === tab).match) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-bold">My complaints</h1>
        <Link to="/complaints/new" className="btn btn-primary">
          + Report new complaint
        </Link>
      </div>

      <div className="flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-full px-3 py-1 text-sm ${tab === t.key ? "bg-blue-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
          >
            {t.label}
            {items && <span className="ml-1 opacity-70">{items.filter(t.match).length}</span>}
          </button>
        ))}
      </div>

      <ErrorBox message={error} onRetry={load} />
      {items === null && !error && <PageLoader />}

      {items && shown.length === 0 && (
        <EmptyState title={items.length ? "Nothing here" : "You haven't reported anything yet"}>
          <Link to="/complaints/new" className="text-blue-700 hover:underline">
            Report an issue
          </Link>
        </EmptyState>
      )}

      <ul className="space-y-3">
        {shown.map((c) => (
          <li key={c.ticket_no}>
            <Link to={`/complaints/${c.ticket_no}`} className="card flex gap-3 transition hover:border-blue-300 hover:shadow">
              {c.thumbnail_url ? (
                <img src={mediaUrl(c.thumbnail_url)} alt="" className="h-16 w-16 flex-none rounded-lg object-cover" />
              ) : (
                <div className="flex h-16 w-16 flex-none items-center justify-center rounded-lg bg-slate-100 text-xl">📝</div>
              )}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold">{c.ticket_no}</span>
                  <StatusBadge status={c.status} />
                </div>
                <p className="text-sm font-medium">{c.category?.name || "Category under review"}</p>
                <p className="line-clamp-1 text-sm text-slate-600">{c.description}</p>
                <p className="text-xs text-slate-500">
                  Filed {timeAgo(c.created_at)} · updated {timeAgo(c.updated_at)}
                  {c.assigned_officer_name && ` · Officer: ${c.assigned_officer_name}`}
                  {c.upvote_count > 0 && ` · ${c.upvote_count} 👍`}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
