export const STATUS_META = {
  SUBMITTED: { label: "Submitted", cls: "bg-slate-100 text-slate-700", dot: "bg-slate-400" },
  TRIAGE: { label: "Under review", cls: "bg-amber-100 text-amber-800", dot: "bg-amber-500" },
  OPEN: { label: "Open", cls: "bg-blue-100 text-blue-800", dot: "bg-blue-500" },
  ASSIGNED: { label: "Officer assigned", cls: "bg-indigo-100 text-indigo-800", dot: "bg-indigo-500" },
  IN_PROGRESS: { label: "In progress", cls: "bg-purple-100 text-purple-800", dot: "bg-purple-500" },
  RESOLVED: { label: "Resolved", cls: "bg-green-100 text-green-800", dot: "bg-green-500" },
  REJECTED: { label: "Rejected", cls: "bg-red-100 text-red-800", dot: "bg-red-500" },
};

// Hex colours for map markers (Tailwind classes don't reach Leaflet SVG)
export const STATUS_COLORS = {
  TRIAGE: "#f59e0b",
  OPEN: "#3b82f6",
  ASSIGNED: "#6366f1",
  IN_PROGRESS: "#a855f7",
  RESOLVED: "#22c55e",
  REJECTED: "#ef4444",
};

export const ACTIVE_STATUSES = ["TRIAGE", "OPEN", "ASSIGNED", "IN_PROGRESS"];

export const SEVERITIES = [
  { value: "low", label: "Low", hint: "Minor inconvenience" },
  { value: "medium", label: "Medium", hint: "Affects daily life" },
  { value: "high", label: "High", hint: "Serious, needs quick action" },
  { value: "critical", label: "Critical", hint: "Danger to life or property" },
];

// Quick picks for the location screen: handy on demo day when GPS puts you
// somewhere outside the demo wards. The last one shows the triage path.
export const DEMO_PLACES = [
  { label: "Pari Chowk, Greater Noida", lat: 28.466, lng: 77.509 },
  { label: "Knowledge Park II, Greater Noida", lat: 28.4592, lng: 77.4968 },
  { label: "Gaur Chowk, Greater Noida West", lat: 28.6045, lng: 77.4345 },
  { label: "Sector 18 Market, Noida", lat: 28.5705, lng: 77.3215 },
  { label: "Sector 62, Noida", lat: 28.627, lng: 77.365 },
  { label: "Connaught Place, Delhi (outside service area)", lat: 28.6315, lng: 77.2167 },
];

export const LIMITS = { maxPhotos: 3, maxPhotoMB: 5, maxVideoMB: 25 };

export function formatDateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function timeAgo(iso) {
  if (!iso) return "";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

/** Compact age for officer tables: "45m", "6h", "3d 4h". */
export function ageLabel(iso) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days}d ${hours % 24}h` : `${days}d`;
}

export function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortAddress(address, max = 60) {
  if (!address) return "";
  return address.length > max ? `${address.slice(0, max - 1)}…` : address;
}
