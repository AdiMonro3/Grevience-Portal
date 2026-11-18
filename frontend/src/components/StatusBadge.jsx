import { STATUS_META } from "../lib/format";

export default function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status, cls: "bg-slate-100 text-slate-700" };
  return <span className={`badge ${meta.cls}`}>{meta.label}</span>;
}

const PRIORITY_CLS = {
  P1: "bg-red-600 text-white",
  P2: "bg-orange-500 text-white",
  P3: "bg-yellow-300 text-yellow-900",
  P4: "bg-slate-200 text-slate-700",
};

export function PriorityBadge({ label, score }) {
  return (
    <span className={`badge ${PRIORITY_CLS[label] || PRIORITY_CLS.P4}`} title={`Priority score ${score}`}>
      {label}
      {score != null && <span className="ml-1 font-normal opacity-80">{score}</span>}
    </span>
  );
}
