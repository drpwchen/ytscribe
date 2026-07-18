"""VTT -> plain text.

Strips timestamps, inline karaoke tags, and YouTube's rolling-caption
duplicates (the same line repeated as it scrolls up the screen).
"""
from __future__ import annotations

import pathlib
import re

_TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
_TAG = re.compile(r"<[^>]+>")
_SKIP_PREFIX = ("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")


def vtt_to_text(path: str | pathlib.Path) -> str:
    lines = pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    prev: str | None = None

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(_SKIP_PREFIX):
            continue
        if _TIMESTAMP.match(line) or line.isdigit():
            continue

        line = _TAG.sub("", line).replace("&nbsp;", " ").strip()
        if not line or line == prev:
            continue

        out.append(line)
        prev = line

    return "\n".join(out)
