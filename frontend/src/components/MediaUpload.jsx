import { useEffect, useRef, useState } from "react";
import { LIMITS, formatBytes } from "../lib/format";

/** Preview for one local File; the object URL is released when it unmounts. */
function FilePreview({ file, onRemove }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  const isVideo = file.type.startsWith("video/");
  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
      {url &&
        (isVideo ? (
          <video src={url} className="h-32 w-full object-cover" controls muted />
        ) : (
          <img src={url} alt={file.name} className="h-32 w-full object-cover" />
        ))}
      <div className="flex items-center justify-between gap-1 bg-white px-2 py-1 text-xs text-slate-600">
        <span className="truncate">{formatBytes(file.size)}</span>
        <button type="button" onClick={onRemove} className="font-medium text-red-600 hover:underline">
          Remove
        </button>
      </div>
    </div>
  );
}

/**
 * Photo + video picker with previews and client-side checks (count, type, size).
 * The server checks again; this just gives instant feedback.
 */
export default function MediaUpload({ photos, onPhotosChange, video, onVideoChange, allowVideo = true }) {
  const photoInput = useRef(null);
  const videoInput = useRef(null);
  const [error, setError] = useState("");

  function addPhotos(e) {
    const picked = Array.from(e.target.files || []);
    e.target.value = ""; // allow picking the same file again after removing it
    const problems = [];
    const ok = [];
    for (const f of picked) {
      if (!f.type.startsWith("image/")) problems.push(`${f.name} is not an image`);
      else if (f.size > LIMITS.maxPhotoMB * 1024 * 1024)
        problems.push(`${f.name} is ${formatBytes(f.size)} (max ${LIMITS.maxPhotoMB} MB)`);
      else ok.push(f);
    }
    const room = LIMITS.maxPhotos - photos.length;
    if (ok.length > room) problems.push(`Only ${LIMITS.maxPhotos} photos allowed`);
    onPhotosChange([...photos, ...ok.slice(0, Math.max(room, 0))]);
    setError(problems.join(". "));
  }

  function addVideo(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (!f.type.startsWith("video/")) return setError(`${f.name} is not a video`);
    if (f.size > LIMITS.maxVideoMB * 1024 * 1024)
      return setError(`${f.name} is ${formatBytes(f.size)} (max ${LIMITS.maxVideoMB} MB)`);
    setError("");
    onVideoChange(f);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={photos.length >= LIMITS.maxPhotos}
          onClick={() => photoInput.current.click()}
        >
          📷 Add photos ({photos.length}/{LIMITS.maxPhotos})
        </button>
        {allowVideo && (
          <button type="button" className="btn btn-secondary" disabled={!!video} onClick={() => videoInput.current.click()}>
            🎥 Add video ({video ? 1 : 0}/1)
          </button>
        )}
        <input ref={photoInput} type="file" accept="image/*" multiple hidden onChange={addPhotos} />
        <input ref={videoInput} type="file" accept="video/*" hidden onChange={addVideo} />
      </div>
      <p className="text-xs text-slate-500">
        Photos up to {LIMITS.maxPhotoMB} MB each{allowVideo && `, one video up to ${LIMITS.maxVideoMB} MB`}.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {(photos.length > 0 || video) && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {photos.map((f, i) => (
            <FilePreview
              key={`${f.name}-${f.lastModified}-${i}`}
              file={f}
              onRemove={() => onPhotosChange(photos.filter((_, j) => j !== i))}
            />
          ))}
          {video && <FilePreview file={video} onRemove={() => onVideoChange(null)} />}
        </div>
      )}
    </div>
  );
}
