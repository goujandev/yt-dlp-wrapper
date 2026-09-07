"""yt-dlp glue: probing a URL for available quality presets, and downloading.

This module is deliberately Qt-free so it can be exercised from a plain script.
Callers pass in plain callables for progress/log reporting; the Qt layer in
worker.py adapts those to signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import yt_dlp

from .ffmpeg_tools import find_ffmpeg, missing_ffmpeg_message

try:  # yt-dlp exposes this from 2023.07 onwards; fall back for older releases.
    from yt_dlp.utils import DownloadCancelled
except ImportError:  # pragma: no cover - depends on installed yt-dlp
    class DownloadCancelled(Exception):
        pass


# A long dropdown defeats the point of simple presets, so cap the number of
# per-resolution entries; the highest ones are kept.
MAX_QUALITY_ENTRIES = 8

# Friendlier names for the resolutions people recognise. Anything else falls
# back to a plain "<height>p".
LADDER_LABELS = {
    2160: "2160p (4K)",
    1440: "1440p (2K)",
    1080: "1080p (Full HD)",
    720: "720p (HD)",
    480: "480p",
    360: "360p",
}


class GrabItError(Exception):
    """An error worth showing to the user verbatim."""


@dataclass(frozen=True)
class Preset:
    """One entry in the quality dropdown."""

    label: str
    format_selector: str
    audio_only: bool = False


@dataclass(frozen=True)
class VideoInfo:
    title: str
    duration: str
    uploader: str
    presets: list


def _format_duration(seconds) -> str:
    if not seconds:
        return "unknown length"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _friendly_error(exc: Exception) -> str:
    """Turn a yt-dlp exception into something a non-technical user can act on."""
    text = str(exc)
    # yt-dlp prefixes messages with "ERROR: " and may embed ANSI colour codes.
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = re.sub(r"^ERROR:\s*", "", text).strip()

    lowered = text.lower()
    if "unsupported url" in lowered or "is not a valid url" in lowered:
        return "That link is not a video URL GrabIt recognises. Check it and try again."
    if "video unavailable" in lowered or "private video" in lowered:
        return "This video is unavailable - it may be private, deleted, or region locked."
    if "sign in" in lowered or "age-restricted" in lowered:
        return (
            "This video requires signing in (age-restricted or members-only), "
            "so it cannot be downloaded."
        )
    if any(t in lowered for t in ("urlopen error", "timed out", "connection",
                                  "network", "getaddrinfo", "temporary failure")):
        return "Network problem - check your internet connection and try again."
    if "http error 404" in lowered:
        return "That page could not be found (404). Double-check the link."
    if "http error 403" in lowered:
        return (
            "The site refused the download (403). This is usually temporary - "
            "wait a moment and try again."
        )
    if "no space left" in lowered or "not enough space" in lowered:
        return "The drive is out of space. Free some room or pick another folder."
    if "permission denied" in lowered or "access is denied" in lowered:
        return "GrabIt could not write to that folder. Pick a different output folder."
    return text or "Something went wrong."


def build_presets(info: dict) -> list:
    """Work out which simple presets this URL can actually deliver."""
    formats = info.get("formats") or []

    heights = {
        f.get("height")
        for f in formats
        if f.get("vcodec") not in (None, "none") and f.get("height")
    }
    has_video = bool(heights)
    has_audio = any(f.get("acodec") not in (None, "none") for f in formats)

    presets = []

    if has_video:
        presets.append(Preset("Best available quality", "bv*+ba/b"))
        # One entry per height the source genuinely offers. Deriving the list
        # from the real formats rather than a fixed ladder avoids offering two
        # rungs that would download the same stream.
        for height in sorted(heights, reverse=True)[:MAX_QUALITY_ENTRIES]:
            presets.append(
                Preset(
                    LADDER_LABELS.get(height, f"{height}p"),
                    "bv*[height<=%d]+ba/b[height<=%d]/wv*+ba/w" % (height, height),
                )
            )

    if has_audio:
        presets.append(Preset("Audio only (MP3, 320 kbps)", "ba/b", audio_only=True))

    if not presets:
        raise GrabItError("No downloadable video or audio was found at that link.")

    return presets


def probe(url: str) -> VideoInfo:
    """Fetch metadata and available presets. Blocking - call from a worker."""
    url = url.strip()
    if not url:
        raise GrabItError("Paste a video link first.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise GrabItError(
            "That does not look like a link. It should start with http:// or https://."
        )

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 - never let the worker die unexplained
        raise GrabItError(_friendly_error(exc)) from exc

    if info is None:
        raise GrabItError("Nothing could be read from that link.")

    # A playlist URL still resolves. v1 handles single videos only, so take the
    # first entry; the UI tells the user that is what happened.
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise GrabItError("That link is a playlist with no playable videos.")
        info = entries[0]

    return VideoInfo(
        title=info.get("title") or "Untitled",
        duration=_format_duration(info.get("duration")),
        uploader=info.get("uploader") or info.get("extractor_key") or "",
        presets=build_presets(info),
    )


def download(
    url: str,
    preset: Preset,
    output_dir: str,
    on_progress: Callable[[dict], None],
    on_log: Callable[[str], None],
    is_cancelled: Callable[[], bool],
) -> str:
    """Download the URL into output_dir and return the final file path.

    Blocking - call from a worker thread.
    """
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        raise GrabItError(missing_ffmpeg_message())

    finished = {"path": ""}

    def hook(status: dict) -> None:
        if is_cancelled():
            raise DownloadCancelled("Cancelled by user.")
        on_progress(status)
        if status.get("status") == "finished":
            finished["path"] = status.get("filename", "") or finished["path"]

    # yt-dlp starts a postprocessor once per stream, so a merge or an audio
    # extraction can announce itself several times for one download. The user
    # only needs to be told the stage began.
    announced: set[str] = set()

    def postprocessor_hook(status: dict) -> None:
        if is_cancelled():
            raise DownloadCancelled("Cancelled by user.")
        name = status.get("postprocessor", "")
        if status.get("status") == "started" and name not in announced:
            announced.add(name)
            if name == "Merger":
                on_log("merging video and audio")
            elif name in ("FFmpegExtractAudio", "ExtractAudio"):
                on_log("converting to mp3")
        elif status.get("status") == "finished":
            info = status.get("info_dict") or {}
            path = info.get("filepath") or info.get("_filename")
            if path:
                finished["path"] = path

    opts = {
        "outtmpl": {"default": output_dir.rstrip("/\\") + "/%(title)s.%(ext)s"},
        "format": preset.format_selector,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ffmpeg_location": ffmpeg_path,
        "progress_hooks": [hook],
        "postprocessor_hooks": [postprocessor_hook],
        "windowsfilenames": True,
        "retries": 3,
        "fragment_retries": 3,
    }

    if preset.audio_only:
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ]
    else:
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadCancelled:
        raise
    except Exception as exc:  # noqa: BLE001
        # A cancel raised inside a hook can surface wrapped in DownloadError.
        if is_cancelled():
            raise DownloadCancelled("Cancelled by user.") from exc
        raise GrabItError(_friendly_error(exc)) from exc

    if isinstance(info, dict):
        requested = info.get("requested_downloads") or []
        path = info.get("filepath") or (requested[0].get("filepath") if requested else None)
        if path:
            finished["path"] = path

    return finished["path"]
