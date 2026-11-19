import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import StatusBadge, { PriorityBadge, ReopenedBadge } from "../../components/StatusBadge";
import { EmptyState, ErrorBox, PageLoader } from "../../components/States";
import { ageLabel, dueLabel } from "../../lib/format";

const FILTERS = [
  { key: "active", label: "Active", statuses: ["OPEN", "ASSIGNED", "IN_PROGRESS"] },
  { key: "overdue", label: "⚠ Overdue", test: (c) => c.overdue },
  { key: "OPEN", label: "Open", statuses: ["OPEN"] },
  { key: "ASSIGNED", label: "Assigned", statuses: ["ASSIGNED"] },
  { key: "IN_PROGRESS", label: "In progress", statuses: ["IN_PROGRESS"] },
  { key: "RESOLVED", label: "Resolved", statuses: ["RESOLVED"] },
  { key: "REJECTED", label: "Rejected", statuses: ["REJECTED"] },
  { key: "all", label: "All", statuses: null },
];
const REFRESH_MS = 20000;

export default function Queue() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("active");

  // One call for the whole jurisdiction; tabs filter client-side so counts are instant.
  const load = useCallback(() => {
    api
      .get("/officer/queue")
      .then((r) => {
        setItems(r.data);
        setError("");
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS); // new complaints show up during the demo
    return () => clearInterval(timer);
  }, [load]);

  const matches = (f, c) => (f.test ? f.test(c) : !f.statuses || f.statuses.includes(c.status));
  const current = FILTERS.find((f) => f.key === filter);
  const shown = items?.filter((c) => matches(current, c)) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">My queue</h1>
          <p className="text-sm text-slate-500">
            {user.department?.name} · {user.ward?.name} · highest priority first, then oldest
          </p>
        </div>
        <button onClick={load} className="btn btn-secondary btn-sm">
          ↻ Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-full px-3 py-1 text-sm ${filter === f.key ? "bg-blue-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
          >
            {f.label}
            {items && <span className="ml-1 opacity-70">{items.filter((c) => matches(f, c)).length}</span>}
          </button>
        ))}
      </div>

      <ErrorBox message={error} onRetry={load} />
      {items === null && !error && <PageLoader />}
      {items && shown.length === 0 && <EmptyState title="No tickets here">New complaints in your ward appear automatically.</EmptyState>}

      {shown.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[840px] text-left text-sm">
            <thead className="bg-slate-50 text-xs tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Ticket</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3">Age</th>
                <th className="px-4 py-3" title="Target fix time from the category's SLA">Due</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" title="Me too votes">👍</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((c) => (
                <tr
                  key={c.ticket_no}
                  onClick={() => navigate(`/officer/tickets/${c.ticket_no}`)}
                  className="cursor-pointer hover:bg-blue-50"
                >
                  <td className="px-4 py-3">
                    <PriorityBadge label={c.priority_label} score={c.priority} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold">{c.ticket_no}</td>
                  <td className="px-4 py-3">{c.category?.name}</td>
                  <td className="max-w-xs px-4 py-3">
                    <span className="line-clamp-1 text-slate-600">{c.description}</span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">{ageLabel(c.created_at)}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {c.overdue ? (
                      <span className="font-medium text-red-700">⚠ {dueLabel(c.due_at)}</span>
                    ) : c.due_at && !["RESOLVED", "REJECTED"].includes(c.status) ? (
                      <span className="text-slate-600">{dueLabel(c.due_at)}</span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      <StatusBadge status={c.status} />
                      <ReopenedBadge count={c.reopen_count} />
                    </div>
                    {c.assigned_officer_name && c.assigned_officer_name !== user.name && (
                      <div className="mt-0.5 text-xs text-slate-500">{c.assigned_officer_name}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{c.upvote_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
