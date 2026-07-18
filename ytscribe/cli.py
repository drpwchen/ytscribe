"""ytscribe — fetch transcripts for a whole YouTube channel."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

from . import asr as asr_mod
from .subs import DEFAULT_LANGS, fetch_subtitle, lang_of, list_videos
from .vtt import vtt_to_text

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(title: str, limit: int = 70) -> str:
    return _UNSAFE.sub("", title).strip()[:limit].strip() or "untitled"


def write_note(path: pathlib.Path, meta: dict, text: str) -> None:
    front = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items())
    path.write_text(f"---\n{front}\n---\n\n{text}\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ytscribe",
        description="Fetch YouTube transcripts (subtitles first, local Whisper as fallback).",
    )
    p.add_argument("url", help="Channel, playlist, or video URL")
    p.add_argument("-o", "--out", default="transcripts", help="Output directory")
    p.add_argument("--langs", default=DEFAULT_LANGS, help="Native subtitle tracks, priority order")
    p.add_argument("--whisper", action="store_true",
                   help="Transcribe locally when a video has no subtitles")
    p.add_argument("--model", default="large-v3",
                   help="faster-whisper model name or local CTranslate2 path")
    p.add_argument("--device", default="cuda")
    p.add_argument("--compute-type", default="float16")
    p.add_argument("--beam-size", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=4,
                   help="Keep at 4 on an 8 GB card; 8 overflows into shared memory")
    p.add_argument("--language", default=None, help="Force a language code, e.g. zh")
    p.add_argument("--vad", action="store_true",
                   help="Enable VAD + batched inference: ~2x faster, but drops quiet speech")
    p.add_argument("--keep-audio", action="store_true",
                   help="Keep downloaded audio (deleted by default)")
    p.add_argument("--only", default=None,
                   help="Comma-separated video IDs to restrict the run to")
    p.add_argument("--sleep", type=float, default=1.5, help="Delay between videos, seconds")
    args = p.parse_args(argv)

    out = pathlib.Path(args.out)
    vtt_dir = out / "_vtt"
    audio_dir = out / "_audio"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/2] Listing videos from {args.url}", flush=True)
    videos = list_videos(args.url)
    if args.only:
        wanted = {v.strip() for v in args.only.split(",") if v.strip()}
        videos = [v for v in videos if v["id"] in wanted]
    print(f"      {len(videos)} video(s)", flush=True)

    print("[2/2] Fetching transcripts", flush=True)
    made = skipped = whispered = 0
    missing: list[str] = []

    for i, v in enumerate(videos, 1):
        vid, title = v["id"], v["title"]
        note = out / f"{safe_name(title)} [{vid}].md"
        tag = f"[{i}/{len(videos)}]"

        if note.exists():
            skipped += 1
            continue

        meta = {
            "title": title,
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "duration_sec": v["duration"],
        }

        sub = fetch_subtitle(vid, vtt_dir, args.langs)
        if sub:
            text = vtt_to_text(sub)
            meta |= {"sub_lang": lang_of(sub), "source": "youtube-subtitles"}
            write_note(note, meta, text)
            made += 1
            print(f"  {tag} sub  {meta['sub_lang']:<7} {len(text):>6} chars  {title[:45]}", flush=True)
            time.sleep(args.sleep)
            continue

        if not args.whisper:
            missing.append(f"{vid} | {title}")
            print(f"  {tag} ---  no subtitles     {title[:45]}", flush=True)
            continue

        audio = None
        try:
            audio = asr_mod.download_audio(vid, audio_dir)
            text, detected = asr_mod.transcribe(
                audio, model=args.model, device=args.device,
                compute_type=args.compute_type, beam_size=args.beam_size,
                batch_size=args.batch_size, language=args.language,
                vad_filter=args.vad,
            )
            meta |= {"sub_lang": detected, "source": f"whisper:{pathlib.Path(args.model).name}"}
            write_note(note, meta, text)
            whispered += 1
            print(f"  {tag} ASR  {detected:<7} {len(text):>6} chars  {title[:45]}", flush=True)
        except Exception as exc:  # noqa: BLE001 — one bad video must not kill the batch
            missing.append(f"{vid} | {title} ({exc})")
            print(f"  {tag} !!!  {str(exc)[:80]}", flush=True)
        finally:
            if audio and not args.keep_audio and audio.exists():
                audio.unlink()

    print(f"\nDone: {made} from subtitles, {whispered} via Whisper, {skipped} already present", flush=True)
    if missing:
        print(f"\nNo transcript ({len(missing)}):", flush=True)
        for m in missing:
            print(f"  {m}", flush=True)
    if not args.keep_audio and audio_dir.exists() and not any(audio_dir.iterdir()):
        audio_dir.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
