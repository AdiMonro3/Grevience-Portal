import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router";
import { api, errorMessage, mediaUrl } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import MapView from "../../components/MapView";
import StatusBadge from "../../components/StatusBadge";
import { EmptyState, ErrorBox, PageLoader } from "../../components/States";
import { STATUS_COLORS, STATUS_META, shortAddress, timeAgo } from "../../lib/format";

function MeTooButton({ item, busy, onClick }) {
  if (item.mine) {
    return (
      <Link to={`/complaints/${item.ticket_no}`} className="btn btn-secondary btn-sm">
        Yours · {item.upvote_count} 👍
      </Link>
    );
  }
  if (item.i_upvoted) {
    return (
      <span className="btn btn-sm cursor-default bg-green-50 text-green-800 ring-1 ring-green-200" title="You said Me too">
        ✓ Me too · {item.upvote_count}
      </span>
    );
  }
  return (
    <button className="btn btn-primary btn-sm" onClick={onClick} disabled={busy}>
      👍 Me too · {item.upvote_count}
    </button>
  );
}

function NearbyCard({ item, busy, onMeToo }) {
  return (
    <li className="card flex gap-3">
      {item.thumbnail_url ? (
        <img src={mediaUrl(item.thumbnail_url)} alt="" className="h-14 w-14 flex-none rounded-lg object-cover sm:h-20 sm:w-20" />
      ) : (
        <div className="flex h-14 w-14 flex-none items-center justify-center rounded-lg bg-slate-100 text-2xl sm:h-20 sm:w-20">📝</div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{item.category?.name || "Under review"}</span>
          <StatusBadge status={item.status} />
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-slate-700">{item.description}</p>
        <p className="mt-1 text-xs text-slate-500">
          {item.distance_km < 1 ? `${Math.round(item.distance_km * 1000)} m` : `${item.distance_km} km`} away ·{" "}
          {timeAgo(item.created_at)}
          {item.address && ` · ${shortAddress(item.address, 40)}`}
        </p>
        <div className="mt-2 sm:hidden">
          <MeTooButton item={item} busy={busy} onClick={() => onMeToo(item)} />
        </div>
      </div>
      <div className="hidden flex-none self-center sm:block">
        <MeTooButton item={item} busy={busy} onClick={() => onMeToo(item)} />
      </div>
    </li>
  );
}

export default function Nearby() {
  const { user } = useAuth();
  const [radius, setRadius] = useState(3);
  const [includeResolved, setIncludeResolved] = useState(false);
  const [view, setView] = useState("list");
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [busyTicket, setBusyTicket] = useState(null);

  const load = useCallback(async () => {
    if (user.lat == null) return;
    setError("");
    try {
      const { data } = await api.get("/complaints/nearby", {
        params: { lat: user.lat, lng: user.lng, radius_km: radius, include_resolved: includeResolved },
      });
      setItems(data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [user.lat, user.lng, radius, includeResolved]);

  useEffect(() => {
    load();
  }, [load]);

  if (user.lat == null) return <Navigate to="/location" replace />;

  async function meToo(item) {
    setBusyTicket(item.ticket_no);
    try {
      const { data } = await api.post(`/complaints/${item.ticket_no}/upvote`);
      setItems((list) =>
        list.map((i) => (i.ticket_no === item.ticket_no ? { ...i, upvote_count: data.upvote_count, i_upvoted: true } : i)),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyTicket(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Issues near you</h1>
          <p className="text-sm text-slate-500">
            📍 {shortAddress(user.address, 50) || "Your saved location"} ·{" "}
            <Link to="/location" className="text-blue-700 hover:underline">
              change
            </Link>
          </p>
        </div>
        <Link to="/complaints/new" className="btn btn-primary">
          + Report new complaint
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select className="input w-auto" value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
          {[1, 3, 5, 10].map((r) => (
            <option key={r} value={r}>
              Within {r} km
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={includeResolved} onChange={(e) => setIncludeResolved(e.target.checked)} />
          Show resolved
        </label>
        <div className="ml-auto inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
          {["list", "map"].map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1.5 text-sm capitalize ${view === v ? "bg-blue-700 text-white" : "text-slate-600"}`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      <p className="rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-900">
        Is your problem already listed? Tap <b>Me too</b> instead of filing a duplicate. It moves the complaint up the officer's queue.
      </p>

      <ErrorBox message={error} onRetry={load} />

      {items === null && !error && <PageLoader />}

      {items && view === "map" && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
          <span className="flex items-center gap-1">
            <span className="h-3 w-3 rounded-full bg-slate-900" /> You
          </span>
          {["TRIAGE", "OPEN", "ASSIGNED", "IN_PROGRESS", ...(includeResolved ? ["RESOLVED"] : [])].map((s) => (
            <span key={s} className="flex items-center gap-1">
              <span className="h-3 w-3 rounded-full" style={{ background: STATUS_COLORS[s] }} /> {STATUS_META[s].label}
            </span>
          ))}
        </div>
      )}

      {items && view === "map" && (
        <MapView
          center={[user.lat, user.lng]}
          zoom={radius <= 1 ? 15 : radius <= 3 ? 14 : 12}
          className="h-112"
          markers={[
            { id: "me", lat: user.lat, lng: user.lng, color: "#0f172a", radius: 7, tooltip: "You" },
            ...items.map((i) => ({
              id: i.ticket_no,
              lat: i.lat,
              lng: i.lng,
              color: STATUS_COLORS[i.status],
              popup: (
                <div className="space-y-1">
                  <div className="font-semibold">{i.category?.name || "Under review"}</div>
                  <div className="text-xs">{shortAddress(i.description, 90)}</div>
                  <div className="text-xs text-slate-500">
                    {i.upvote_count} 👍 · {timeAgo(i.created_at)}
                  </div>
                  {!i.mine && !i.i_upvoted && (
                    <button className="btn btn-primary btn-sm mt-1" onClick={() => meToo(i)}>
                      👍 Me too
                    </button>
                  )}
                </div>
              ),
            })),
          ]}
        />
      )}

      {items && view === "list" && items.length === 0 && (
        <EmptyState title={`No open complaints within ${radius} km`}>
          Spotted a problem? <Link to="/complaints/new" className="text-blue-700 hover:underline">Report it</Link>.
        </EmptyState>
      )}

      {items && view === "list" && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((item) => (
            <NearbyCard key={item.ticket_no} item={item} busy={busyTicket === item.ticket_no} onMeToo={meToo} />
          ))}
        </ul>
      )}
    </div>
  );
}
