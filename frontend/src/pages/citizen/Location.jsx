import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import MapView from "../../components/MapView";
import { ErrorBox, Notice, Spinner } from "../../components/States";
import { DEMO_PLACES } from "../../lib/format";

const DEFAULT_CENTER = [28.52, 77.42]; // between Noida and Greater Noida

export default function Location() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/nearby";

  const [point, setPoint] = useState(
    user.lat != null ? { lat: user.lat, lng: user.lng, address: user.address || "" } : null,
  );
  const [ward, setWard] = useState(undefined); // undefined = checking/unknown, null = outside all wards
  const [wards, setWards] = useState([]);
  const [gpsBusy, setGpsBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/wards").then((r) => setWards(r.data)).catch(() => {});
  }, []);

  // Tell the citizen right away whether this point is inside a ward
  const lat = point?.lat;
  const lng = point?.lng;
  useEffect(() => {
    if (lat == null) return;
    let cancelled = false;
    setWard(undefined);
    api
      .get("/geo/ward", { params: { lat, lng } })
      .then((r) => !cancelled && setWard(r.data.ward))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [lat, lng]);

  async function choose(newLat, newLng, address) {
    setError("");
    setPoint({ lat: newLat, lng: newLng, address: address ?? "" });
    if (address != null) return;
    // Best effort: turn coordinates into a readable address (needs internet)
    try {
      const { data } = await api.get("/geo/reverse", { params: { lat: newLat, lng: newLng } });
      if (data.address) {
        setPoint((p) => (p && p.lat === newLat && p.lng === newLng ? { ...p, address: data.address } : p));
      }
    } catch {
      /* keep the address box empty; the citizen can type one */
    }
  }

  function useGps() {
    if (!navigator.geolocation) {
      setError("This browser can't share your location. Search for your address instead.");
      return;
    }
    setGpsBusy(true);
    setError("");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsBusy(false);
        choose(pos.coords.latitude, pos.coords.longitude);
      },
      (err) => {
        setGpsBusy(false);
        setError(
          err.code === 1
            ? "Location permission was denied. Allow it in your browser, or search for your address."
            : "Couldn't get your location. Search for your address instead.",
        );
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function search(e) {
    e.preventDefault();
    if (query.trim().length < 3) return;
    setSearching(true);
    setResults(null);
    setError("");
    try {
      const { data } = await api.get("/geo/geocode", { params: { q: query.trim() } });
      setResults(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const { data } = await api.put("/users/me/location", {
        lat: point.lat,
        lng: point.lng,
        address: point.address?.trim() || null,
      });
      setUser(data);
      navigate(next);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Where is the problem?</h1>
        <p className="text-sm text-slate-500">We use this to show complaints near you and route yours to the right ward.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <div className="card space-y-3">
            <button className="btn btn-primary w-full" onClick={useGps} disabled={gpsBusy}>
              {gpsBusy ? <Spinner className="h-4 w-4 text-white" /> : "📍"} Use my current location
            </button>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <div className="h-px flex-1 bg-slate-200" /> or type an address <div className="h-px flex-1 bg-slate-200" />
            </div>
            <form onSubmit={search} className="flex gap-2">
              <input
                className="input"
                placeholder="e.g. Pari Chowk, Greater Noida"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button className="btn btn-secondary" disabled={searching || query.trim().length < 3}>
                {searching ? <Spinner className="h-4 w-4" /> : "Search"}
              </button>
            </form>
            {results && results.length === 0 && (
              <p className="text-sm text-slate-500">
                No matches (or the address service is offline). Try a locality below or tap the map.
              </p>
            )}
            {results?.length > 0 && (
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                {results.map((r) => (
                  <li key={`${r.lat},${r.lng}`}>
                    <button
                      className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                      onClick={() => {
                        choose(r.lat, r.lng, r.label);
                        setResults(null);
                      }}
                    >
                      {r.label}
                      <span className={`ml-1 text-xs ${r.ward ? "text-green-700" : "text-amber-700"}`}>
                        · {r.ward ? r.ward.code : "outside service area"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <p className="mb-2 text-sm font-medium text-slate-700">Quick pick a locality</p>
            <div className="flex flex-wrap gap-2">
              {DEMO_PLACES.map((p) => (
                <button key={p.label} className="btn btn-secondary btn-sm" onClick={() => choose(p.lat, p.lng, p.label)}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-3 lg:col-span-3">
          <MapView
            center={point ? [point.lat, point.lng] : DEFAULT_CENTER}
            zoom={point ? 15 : 11}
            className="h-72 sm:h-96"
            markers={point ? [{ id: "me", lat: point.lat, lng: point.lng, color: "#1d4ed8", radius: 11 }] : []}
            polygons={wards.map((w) => ({ id: w.id, positions: w.polygon, label: w.name }))}
            onMapClick={(la, ln) => choose(la, ln)}
          />
          <p className="text-xs text-slate-500">Tip: tap the map to drop the pin exactly where the problem is. Dashed boxes are wards.</p>

          {point && (
            <div className="card space-y-3">
              <div>
                <label className="label" htmlFor="address">Address / landmark</label>
                <input
                  id="address"
                  className="input"
                  value={point.address}
                  onChange={(e) => setPoint({ ...point, address: e.target.value })}
                  placeholder="House no., street, landmark"
                />
                <p className="mt-1 text-xs text-slate-500">
                  {point.lat.toFixed(5)}, {point.lng.toFixed(5)}
                </p>
              </div>
              {ward === undefined ? (
                <p className="text-sm text-slate-500">Checking ward…</p>
              ) : ward ? (
                <Notice tone="success">✅ {ward.name}</Notice>
              ) : (
                <Notice tone="warning">
                  This spot is outside our wards. You can still report it, but it will be reviewed by an admin before routing.
                </Notice>
              )}
              <ErrorBox message={error} />
              <button className="btn btn-primary w-full" onClick={save} disabled={saving}>
                {saving && <Spinner className="h-4 w-4 text-white" />} Save location & continue
              </button>
            </div>
          )}
          {!point && <ErrorBox message={error} />}
        </div>
      </div>
    </div>
  );
}
