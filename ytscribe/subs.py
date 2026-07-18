"""YouTube subtitle fetching via yt-dlp.

Only native language tracks are requested. YouTube also exposes hundreds of
machine-translated tracks (``ab-zh-TW``, ``af-zh-TW``, ...) which are useless
and would explode the download; yt-dlp matches ``--sub-langs`` exactly, so
listing the native codes is enough to avoid them.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

# Priority order of native tracks. Exact-match only.
DEFAULT_LANGS = "zh-TW,zh-Hant,zh,ja,ko,en,en-US"


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def list_videos(channel_url: str) -> list[dict]:
    """Return [{id, title, duration}] for a channel, playlist, or single video."""
    url = channel_url.rstrip("/")
    if "/watch?" in url or "youtu.be/" in url:
        target = url
    elif not url.endswith(("/videos", "/streams", "/shorts")) and "/playlist" not in url:
        target = f"{url}/videos"
    else:
        target = url

    proc = _run(["yt-dlp", "--no-update", "--flat-playlist", "-J", target])
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to list {target}:\n{proc.stderr[-2000:]}")

    data = json.loads(proc.stdout)
    entries = data.get("entries") or [data]
    return [
        {"id": e["id"], "title": e.get("title") or e["id"], "duration": e.get("duration") or 0}
        for e in entries
        if e.get("id")
    ]


def fetch_subtitle(video_id: str, vtt_dir: pathlib.Path, langs: str = DEFAULT_LANGS) -> pathlib.Path | None:
    """Download the best native subtitle track. Returns the .vtt path, or None if the video has none."""
    vtt_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(vtt_dir.glob(f"{video_id}.*.vtt"))
    if existing:
        return existing[0]

    _run([
        "yt-dlp", "--no-update", "--skip-download",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", langs, "--sub-format", "vtt",
        "--retries", "3",
        "-o", str(vtt_dir / "%(id)s.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ])

    found = sorted(vtt_dir.glob(f"{video_id}.*.vtt"))
    return found[0] if found else None


def lang_of(vtt_path: pathlib.Path) -> str:
    """``abc123.zh-TW.vtt`` -> ``zh-TW``"""
    return vtt_path.name.split(".")[-2]
