"""Local ASR fallback for videos that have no subtitle track at all.

Downloads audio only, transcribes with faster-whisper on the GPU, then deletes
the audio file. Nothing is sent to a cloud API and no video is ever kept.

Settings are tuned for an 8 GB card (RTX 3070 Ti). See README for why
``vad_filter`` and ``condition_on_previous_text`` are off by default.
"""
from __future__ import annotations

import gc
import pathlib
import subprocess
import time

_MODEL = None
_MODEL_KEY = None


def download_audio(video_id: str, audio_dir: pathlib.Path, attempts: int = 2) -> pathlib.Path:
    """Grab audio-only (m4a). Never downloads video streams.

    Raises RuntimeError with yt-dlp's own stderr on failure — a bare "download
    failed" tells the user nothing about whether it was a transient network
    blip, a geo block, or a removed video.
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    out = audio_dir / f"{video_id}.m4a"
    if out.exists():
        return out

    last_err = ""
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(
            ["yt-dlp", "--no-update", "-f", "bestaudio[ext=m4a]/bestaudio",
             "--extract-audio", "--audio-format", "m4a", "--retries", "3",
             "--no-progress", "-o", str(audio_dir / "%(id)s.%(ext)s"),
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
        )
        found = sorted(audio_dir.glob(f"{video_id}.*"))
        if found:
            return found[0]
        last_err = (proc.stderr or proc.stdout or "").strip()[-400:]
        if attempt < attempts:
            time.sleep(3)

    raise RuntimeError(f"audio download failed after {attempts} attempts: {last_err}")


def _load(model: str, device: str, compute_type: str):
    """Cache one model per process. Loading two whisper models in a single
    process crashes an 8 GB card (access violation, exit 3221226505)."""
    global _MODEL, _MODEL_KEY
    key = (model, device, compute_type)
    if _MODEL_KEY != key:
        from faster_whisper import WhisperModel
        _MODEL = None
        gc.collect()
        _MODEL = WhisperModel(model, device=device, compute_type=compute_type)
        _MODEL_KEY = key
    return _MODEL


def transcribe(
    audio_path: pathlib.Path,
    model: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    beam_size: int = 3,
    batch_size: int = 4,
    language: str | None = None,
    vad_filter: bool = False,
    condition_on_previous_text: bool = False,
) -> tuple[str, str]:
    """Transcribe one audio file. Returns (text, detected_language)."""
    whisper = _load(model, device, compute_type)

    if vad_filter:
        # Batched inference derives its clips from VAD, so it only works with
        # the filter on. Roughly 2x faster, at the cost documented below.
        from faster_whisper import BatchedInferencePipeline

        segments, info = BatchedInferencePipeline(model=whisper).transcribe(
            str(audio_path),
            beam_size=beam_size,
            batch_size=batch_size,
            language=language,
            vad_filter=True,
            condition_on_previous_text=condition_on_previous_text,
        )
    else:
        # Sequential path. Slower (~0.05xRT vs ~0.025xRT) but VAD silently
        # drops quiet speech, which costs far more in missed content than the
        # extra minutes cost in wall clock.
        segments, info = whisper.transcribe(
            str(audio_path),
            beam_size=beam_size,
            language=language,
            vad_filter=False,
            condition_on_previous_text=condition_on_previous_text,
        )

    lines = [seg.text.strip() for seg in segments if seg.text.strip()]
    return "\n".join(lines), info.language
