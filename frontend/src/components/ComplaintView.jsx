import MapView from "./MapView";
import MediaGallery from "./MediaGallery";
import StatusBadge, { PriorityBadge, ReopenedBadge } from "./StatusBadge";
import Timeline from "./Timeline";
import { ACTIVE_STATUSES, STATUS_COLORS, dueLabel, formatDateTime, timeAgo } from "../lib/format";

function Field({ label, children }) {
  return (
    <div className="py-1.5">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  );
}

const URGENCY = { 1: "Normal", 2: "Elevated", 3: "Urgent" };

/**
 * Full complaint page body. `staff` shows priority, AI routing details and the
 * citizen's contact; `actions` is rendered under the header (officer buttons).
 */
export default function ComplaintView({ complaint: c, staff = false, actions = null }) {
  const report = c.media.filter((m) => m.purpose === "report");
  const proof = c.media.filter((m) => m.purpose === "proof");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-sm text-slate-500">{c.ticket_no}</p>
          <h1 className="text-2xl font-bold">{c.category?.name || "Category under review"}</h1>
          <p className="text-sm text-slate-500">
            Filed {formatDateTime(c.created_at)} ({timeAgo(c.created_at)})
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ReopenedBadge count={c.reopen_count} />
          {staff && <PriorityBadge label={c.priority_label} score={c.priority} />}
          <StatusBadge status={c.status} />
        </div>
      </div>

      {actions}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <section className="card">
            <h2 className="mb-2 font-semibold">Description</h2>
            <p className="text-sm whitespace-pre-wrap text-slate-800">{c.description}</p>
          </section>

          {c.status === "REJECTED" && (
            <section className="card border-red-200 bg-red-50">
              <h2 className="mb-1 font-semibold text-red-900">Rejected</h2>
              <p className="text-sm text-red-900">{c.rejection_reason}</p>
            </section>
          )}

          {c.status === "RESOLVED" && (
            <section className="card space-y-3 border-green-200 bg-green-50">
              <div>
                <h2 className="font-semibold text-green-900">Resolved {c.resolved_at && `on ${formatDateTime(c.resolved_at)}`}</h2>
                {c.resolution_note && <p className="text-sm text-green-900">{c.resolution_note}</p>}
              </div>
              {proof.length > 0 ? (
                <div>
                  <p className="mb-2 text-xs font-semibold tracking-wide text-green-800 uppercase">Proof of work</p>
                  <MediaGallery media={proof} />
                </div>
              ) : (
                <p className="text-xs text-green-800">Closed without photo proof.</p>
              )}
            </section>
          )}

          {c.status !== "RESOLVED" && proof.length > 0 && (
            <section className="card">
              <h2 className="font-semibold">Proof from the earlier fix</h2>
              <p className="mb-3 text-xs text-slate-500">The citizen reopened this complaint after it was marked resolved.</p>
              <MediaGallery media={proof} />
            </section>
          )}

          {report.length > 0 && (
            <section className="card">
              <h2 className="mb-3 font-semibold">Photos & video</h2>
              <MediaGallery media={report} />
            </section>
          )}

          <section className="card space-y-3">
            <div>
              <h2 className="font-semibold">Location</h2>
              <p className="text-sm text-slate-700">{c.address || "No address given"}</p>
              {c.lat != null && (
                <p className="text-xs text-slate-500">
                  {c.lat.toFixed(5)}, {c.lng.toFixed(5)} ·{" "}
                  <a
                    className="text-blue-700 hover:underline"
                    href={`https://www.google.com/maps?q=${c.lat},${c.lng}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Directions
                  </a>
                </p>
              )}
            </div>
            {c.lat != null && (
              <MapView
                center={[c.lat, c.lng]}
                zoom={16}
                className="h-64"
                markers={[{ id: c.ticket_no, lat: c.lat, lng: c.lng, color: STATUS_COLORS[c.status], radius: 11 }]}
              />
            )}
          </section>
        </div>

        <div className="space-y-4">
          <section className="card">
            <h2 className="mb-1 font-semibold">Details</h2>
            <dl className="divide-y divide-slate-100">
              <Field label="Department">{c.department?.name || "Being reviewed"}</Field>
              <Field label="Ward">{c.ward?.name || "Being reviewed"}</Field>
              {c.due_at && ACTIVE_STATUSES.includes(c.status) && (
                <Field label="Target fix time">
                  {formatDateTime(c.due_at)}
                  <span className={`block text-xs ${c.overdue ? "font-semibold text-red-700" : "font-normal text-slate-600"}`}>
                    {c.overdue ? `⚠ Overdue, ${dueLabel(c.due_at)}` : `Due ${dueLabel(c.due_at)}`}
                  </span>
                </Field>
              )}
              <Field label="Severity (reported)">
                <span className="capitalize">{c.severity}</span>
              </Field>
              <Field label="Me too">{c.upvote_count} {c.upvote_count === 1 ? "person" : "people"}</Field>
              {c.assigned_officer && (
                <Field label="Officer">
                  {c.assigned_officer.name}
                  <a href={`mailto:${c.assigned_officer.email}`} className="block text-xs font-normal text-blue-700 hover:underline">
                    {c.assigned_officer.email}
                  </a>
                </Field>
              )}
              {staff && c.citizen && (
                <Field label="Reported by">
                  {c.citizen.name}
                  <span className="block text-xs font-normal text-slate-600">
                    {c.citizen.email}
                    {c.citizen.phone && ` · ${c.citizen.phone}`}
                  </span>
                </Field>
              )}
            </dl>
          </section>

          {staff && (
            <section className="card">
              <h2 className="mb-1 font-semibold">AI routing</h2>
              <dl className="divide-y divide-slate-100">
                <Field label="Model's category">
                  {c.predicted_category?.name || "—"}
                  {c.ml_confidence != null && (
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-2 flex-1 rounded bg-slate-100">
                        <div
                          className={`h-2 rounded ${c.ml_confidence >= 0.5 ? "bg-green-500" : "bg-amber-500"}`}
                          style={{ width: `${Math.round(c.ml_confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-500">{Math.round(c.ml_confidence * 100)}%</span>
                    </div>
                  )}
                </Field>
                <Field label="Urgency from text">
                  {URGENCY[c.urgency]}
                  {c.urgency_reasons.length > 0 && (
                    <span className="block text-xs font-normal text-slate-600">{c.urgency_reasons.join(", ")}</span>
                  )}
                </Field>
              </dl>
            </section>
          )}

          <section className="card">
            <h2 className="mb-3 font-semibold">Timeline</h2>
            <Timeline history={c.history} />
          </section>
        </div>
      </div>
    </div>
  );
}
