import { mediaUrl } from "../api/client";

export default function MediaGallery({ media }) {
  if (!media?.length) return null;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {media.map((m) =>
        m.kind === "video" ? (
          <video key={m.id} src={mediaUrl(m.url)} controls className="h-44 w-full rounded-lg bg-black object-contain" />
        ) : (
          <a key={m.id} href={mediaUrl(m.url)} target="_blank" rel="noreferrer">
            <img
              src={mediaUrl(m.url)}
              alt="Complaint attachment"
              className="h-44 w-full rounded-lg border border-slate-200 object-cover hover:opacity-90"
            />
          </a>
        ),
      )}
    </div>
  );
}
