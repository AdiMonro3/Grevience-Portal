"""Saving uploaded photos/videos to MEDIA_DIR with random names (S3 in Phase 5)."""

import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.models import MediaKind

PHOTO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
_EXT_TO_TYPE = {ext: ctype for ctype, ext in (PHOTO_TYPES | VIDEO_TYPES).items()} | {
    ".jpeg": "image/jpeg"
}
CHUNK = 1024 * 1024


@dataclass
class SavedFile:
    file_name: str  # relative to MEDIA_DIR, e.g. "complaints/3f2a...jpg"
    original_name: str | None
    content_type: str
    size_bytes: int
    kind: str


def _content_type(upload: UploadFile) -> str:
    ctype = (upload.content_type or "").lower()
    if ctype in PHOTO_TYPES or ctype in VIDEO_TYPES:
        return ctype
    # Some browsers send HEIC/MOV as application/octet-stream: trust the extension
    return _EXT_TO_TYPE.get(Path(upload.filename or "").suffix.lower(), ctype)


def validate_uploads(photos: list[UploadFile], video: UploadFile | None) -> None:
    """Cheap checks before anything touches the disk. Sizes are checked while saving."""
    if len(photos) > settings.max_photos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"At most {settings.max_photos} photos allowed")
    for photo in photos:
        if _content_type(photo) not in PHOTO_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"'{photo.filename}' is not a supported photo (JPG, PNG, WEBP, HEIC)",
            )
    if video is not None and _content_type(video) not in VIDEO_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"'{video.filename}' is not a supported video (MP4, WEBM, MOV)"
        )


async def save_upload(upload: UploadFile, subdir: str) -> SavedFile:
    ctype = _content_type(upload)
    is_photo = ctype in PHOTO_TYPES
    ext = PHOTO_TYPES.get(ctype) or VIDEO_TYPES[ctype]
    max_mb = settings.max_photo_mb if is_photo else settings.max_video_mb
    max_bytes = max_mb * 1024 * 1024

    rel = f"{subdir}/{uuid.uuid4().hex}{ext}"
    dest = settings.media_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"'{upload.filename}' is larger than {max_mb} MB",
                    )
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return SavedFile(
        file_name=rel,
        original_name=upload.filename,
        content_type=ctype,
        size_bytes=size,
        kind=MediaKind.PHOTO if is_photo else MediaKind.VIDEO,
    )


async def save_all(photos: list[UploadFile], video: UploadFile | None, subdir: str) -> list[SavedFile]:
    """Validate and save; if any file fails, remove the ones already written."""
    validate_uploads(photos, video)
    saved: list[SavedFile] = []
    try:
        for upload in [*photos, *([video] if video else [])]:
            saved.append(await save_upload(upload, subdir))
    except BaseException:
        delete_files(saved)
        raise
    return saved


def delete_files(files: list[SavedFile]) -> None:
    for f in files:
        (settings.media_dir / f.file_name).unlink(missing_ok=True)


def media_url(file_name: str) -> str:
    return f"/media/{file_name}"
