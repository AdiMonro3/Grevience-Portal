import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import MediaUpload from "../../components/MediaUpload";
import { ErrorBox, Spinner } from "../../components/States";
import { SEVERITIES, shortAddress } from "../../lib/format";

const MAX_CHARS = 2000;

export default function NewComplaint() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [photos, setPhotos] = useState([]);
  const [video, setVideo] = useState(null);
  const [ward, setWard] = useState(undefined);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user.lat == null) return;
    api
      .get("/geo/ward", { params: { lat: user.lat, lng: user.lng } })
      .then((r) => setWard(r.data.ward))
      .catch(() => {});
  }, [user.lat, user.lng]);

  if (user.lat == null) return <Navigate to="/location?next=/complaints/new" replace />;

  const submitting = progress !== null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (description.trim().length < 10) {
      setError("Please describe the problem in at least 10 characters.");
      return;
    }
    const form = new FormData();
    form.append("description", description.trim());
    form.append("severity", severity);
    form.append("lat", user.lat);
    form.append("lng", user.lng);
    if (user.address) form.append("address", user.address);
    photos.forEach((p) => form.append("photos", p));
    if (video) form.append("video", video);

    setError("");
    setProgress(0);
    try {
      const { data } = await api.post("/complaints", form, {
        onUploadProgress: (ev) => ev.total && setProgress(Math.round((ev.loaded / ev.total) * 100)),
      });
      navigate(`/complaints/${data.ticket_no}/submitted`, { state: { complaint: data } });
    } catch (err) {
      setError(errorMessage(err));
      setProgress(null);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Report an issue</h1>
        <p className="text-sm text-slate-500">
          Describe it in your own words, in English or Hinglish. We'll find the right department automatically.
        </p>
      </div>

      <div className="card flex flex-wrap items-center justify-between gap-2 text-sm">
        <div>
          <span className="text-slate-500">Location: </span>
          <span className="font-medium">{shortAddress(user.address, 70) || `${user.lat.toFixed(4)}, ${user.lng.toFixed(4)}`}</span>
          <div className={`text-xs ${ward ? "text-green-700" : ward === null ? "text-amber-700" : "text-slate-400"}`}>
            {ward ? ward.name : ward === null ? "Outside our wards: an admin will review it" : "Checking ward…"}
          </div>
        </div>
        <Link to="/location?next=/complaints/new" className="btn btn-secondary btn-sm">
          Change
        </Link>
      </div>

      <div className="card space-y-2">
        <label className="label" htmlFor="description">What's the problem?</label>
        <textarea
          id="description"
          className="input min-h-32"
          maxLength={MAX_CHARS}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. Hamari gali mein 3 din se kachra nahi utha, badbu aa rahi hai"
          required
        />
        <p className="text-right text-xs text-slate-400">
          {description.length}/{MAX_CHARS}
        </p>
      </div>

      <div className="card space-y-2">
        <span className="label">How serious is it?</span>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {SEVERITIES.map((s) => (
            <label
              key={s.value}
              className={`cursor-pointer rounded-lg border p-3 text-sm ${
                severity === s.value ? "border-blue-600 bg-blue-50 ring-2 ring-blue-200" : "border-slate-200 hover:bg-slate-50"
              }`}
            >
              <input type="radio" name="severity" value={s.value} checked={severity === s.value} onChange={() => setSeverity(s.value)} className="sr-only" />
              <div className="font-semibold">{s.label}</div>
              <div className="text-xs text-slate-500">{s.hint}</div>
            </label>
          ))}
        </div>
      </div>

      <div className="card space-y-2">
        <span className="label">Photos / video (optional, but they help a lot)</span>
        <MediaUpload photos={photos} onPhotosChange={setPhotos} video={video} onVideoChange={setVideo} />
      </div>

      <ErrorBox message={error} />

      <button className="btn btn-primary w-full py-3 text-base" disabled={submitting}>
        {submitting ? (
          <>
            <Spinner className="h-4 w-4 text-white" />
            {progress < 100 ? `Uploading ${progress}%` : "Routing your complaint…"}
          </>
        ) : (
          "Submit complaint"
        )}
      </button>
    </form>
  );
}
