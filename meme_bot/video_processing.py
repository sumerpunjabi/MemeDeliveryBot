from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .reel_source import MIN_REEL_DURATION_SECONDS, ReelCandidate

LOGGER = logging.getLogger(__name__)


class VideoProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessedVideo:
    path: Path
    video_hash: str
    size_bytes: int
    duration_seconds: float


def calculate_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise VideoProcessingError(f"Required executable not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        raise VideoProcessingError(f"Command failed: {command[0]}{detail}") from exc


def probe_video_duration(path: Path, *, ffprobe_bin: str = "ffprobe") -> float:
    result = _run_command(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise VideoProcessingError(f"Could not read video duration for {path}") from exc


def _ensure_size(path: Path, max_bytes: int) -> int:
    size = path.stat().st_size
    if size <= 0:
        raise VideoProcessingError("Downloaded video is empty")
    if size > max_bytes:
        raise VideoProcessingError(f"Video exceeds maximum size: {size} > {max_bytes}")
    return size


def _ensure_duration(duration_seconds: float, max_duration_seconds: int) -> None:
    if duration_seconds < MIN_REEL_DURATION_SECONDS:
        raise VideoProcessingError(
            f"Video is shorter than {MIN_REEL_DURATION_SECONDS} seconds: {duration_seconds:.2f}"
        )
    if duration_seconds > max_duration_seconds:
        raise VideoProcessingError(
            f"Video exceeds maximum duration: {duration_seconds:.2f} > {max_duration_seconds}"
        )


def download_video(
    candidate: ReelCandidate,
    output_dir: Path,
    *,
    max_bytes: int,
    max_duration_seconds: int,
    yt_dlp_bin: str = "yt-dlp",
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> ProcessedVideo:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"{candidate.reddit_id}-raw.mp4"
    normalized_path = output_dir / f"{candidate.reddit_id}.mp4"

    LOGGER.info("Downloading Reddit video: reddit_id=%s", candidate.reddit_id)
    _run_command(
        [
            yt_dlp_bin,
            "--no-playlist",
            "--format",
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "--merge-output-format",
            "mp4",
            "--output",
            str(raw_path),
            candidate.reddit_permalink or candidate.source_url,
        ]
    )
    _ensure_size(raw_path, max_bytes)

    LOGGER.info("Normalizing Reddit video for Reels: reddit_id=%s", candidate.reddit_id)
    _run_command(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(raw_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(normalized_path),
        ]
    )

    size_bytes = _ensure_size(normalized_path, max_bytes)
    duration_seconds = probe_video_duration(normalized_path, ffprobe_bin=ffprobe_bin)
    _ensure_duration(duration_seconds, max_duration_seconds)
    video_hash = calculate_file_hash(normalized_path)
    return ProcessedVideo(
        path=normalized_path,
        video_hash=video_hash,
        size_bytes=size_bytes,
        duration_seconds=duration_seconds,
    )
