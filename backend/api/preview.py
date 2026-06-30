"""Moment preview API — serves a lightweight, on-the-fly cut of a single moment.

Lets the user watch the found moment (in the source video) BEFORE creating the
full clip. We re-encode just the [start, end] segment to a small 480p mp4 so it:
  - always plays in the browser (source may be .mkv/VP9 which browsers can't play),
  - is cheap and fast (no subtitles / effects / face-crop),
  - is cached, so re-opening the same moment is instant.
"""
import logging
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from backend.config import DOWNLOADS_DIR, TEMP_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

PREVIEW_DIR = TEMP_DIR / "previews"
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

_VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".m4v")
# Posters/thumbnails that live alongside the source video — must NOT be picked
# as the "source" (they're a single frame, not a playable video).
_NON_VIDEO_SUFFIXES = (".webp", ".jpg", ".jpeg", ".png")


def _find_source(video_id: str) -> Path | None:
    """Locate the downloaded source video for a video_id."""
    folder = DOWNLOADS_DIR / video_id
    if not folder.is_dir():
        return None
    # A real source video: a recognized video container that isn't a poster.
    candidates = [p for p in folder.iterdir()
                  if p.is_file()
                  and p.suffix.lower() in _VIDEO_EXTS
                  and p.suffix.lower() not in _NON_VIDEO_SUFFIXES]
    if not candidates:
        return None
    # Prefer a file literally named source.*, else the largest video file.
    named = [p for p in candidates if p.stem.lower() == "source"]
    if named:
        return named[0]
    return max(candidates, key=lambda p: p.stat().st_size)


@router.get("/preview/{video_id}/segment")
async def preview_segment(
    video_id: str,
    start: float = Query(..., ge=0),
    end: float = Query(..., gt=0),
):
    """Return a small mp4 of the moment [start, end] from the source video."""
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    source = _find_source(video_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source video not found")

    duration = round(end - start, 3)
    cache = PREVIEW_DIR / f"{video_id}_{int(start * 1000)}_{int(end * 1000)}.mp4"

    if not cache.exists() or cache.stat().st_size == 0:
        # -ss before -i = fast input seek; re-encode to a browser-safe 480p mp4.
        # -nostdin so a stuck pipe never blocks waiting on console input.
        cmd = [
            "ffmpeg", "-nostdin", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-vf", "scale=-2:480",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            str(cache),
        ]
        logger.info(f"[Preview] Cutting {video_id} {start:.1f}-{end:.1f}s -> {cache.name}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            if cache.exists():
                cache.unlink(missing_ok=True)
            raise HTTPException(status_code=504, detail="Preview generation timed out")
        if proc.returncode != 0 or not cache.exists():
            logger.error(f"[Preview] ffmpeg failed: {proc.stderr[-500:]}")
            if cache.exists():
                cache.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="Failed to generate preview")

    # FileResponse supports HTTP range requests (seeking) out of the box.
    return FileResponse(str(cache), media_type="video/mp4", filename=cache.name)
