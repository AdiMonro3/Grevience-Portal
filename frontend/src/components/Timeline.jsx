import { STATUS_META, formatDateTime } from "../lib/format";

const ROLE_LABEL = { citizen: "Citizen", officer: "Officer", admin: "Admin", system: "System" };

export default function Timeline({ history }) {
  if (!history?.length) return <p className="text-sm text-slate-500">No updates yet.</p>;
  return (
    <ol className="relative ml-2 border-l-2 border-slate-200">
      {history.map((h, i) => {
        const meta = STATUS_META[h.to_status] || STATUS_META.SUBMITTED;
        const last = i === history.length - 1;
        return (
          <li key={h.id} className="relative pb-5 pl-6 last:pb-0">
            <span
              className={`absolute top-1 -left-[9px] h-4 w-4 rounded-full border-2 border-white ${meta.dot} ${
                last ? "ring-4 ring-blue-100" : ""
              }`}
            />
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-sm font-semibold">{meta.label}</span>
              <span className="text-xs text-slate-500">{formatDateTime(h.created_at)}</span>
            </div>
            {h.note && <p className="mt-0.5 text-sm text-slate-700">{h.note}</p>}
            <p className="text-xs text-slate-500">
              {h.actor_name ? `${h.actor_name} · ` : ""}
              {ROLE_LABEL[h.actor_role] || h.actor_role}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
