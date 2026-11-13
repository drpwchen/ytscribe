# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/); this project uses loose semantic versioning.

## [0.1.1] — 2026-11-14 — Docs: README quality pass

Documentation only; the one code change is the version string.

### Docs
- README: Quickstart with the expected console output, a requirements-and-cost section, a Limitations section, and a support line.

## [0.1.0] — 2026-07-30 — Initial public release

Channel-wide YouTube transcript fetching that spends compute only where it has to:
a subtitle track costs a few kilobytes and no GPU, so subtitles are tried first and local
Whisper runs only for videos that have no track at all. Nothing leaves the machine, and no
video file is downloaded or kept.

### Added
- **Subtitles-first fetch over a channel, playlist, or single video** (`ytscribe <url>`).
  One Markdown file per video with YAML frontmatter (`title`, `video_id`, `url`,
  `duration_sec`, `sub_lang`, `source`). `source` is always `youtube-subtitles` or
  `whisper:<model>`, so human-written captions stay distinguishable from machine output
  downstream. Videos already on disk are skipped, which makes a re-run an incremental sync.
- **Local Whisper fallback** (`--whisper`, `[asr]` extra) via `faster-whisper` — used only for
  videos with no subtitle track. Any model `faster-whisper` accepts works, including local
  CTranslate2 fine-tune directories (`--model`); audio is deleted after transcription unless
  `--keep-audio`.
- **Native-language track selection** (`--langs`). YouTube advertises ~200 machine-translated
  tracks per captioned video (`ab-zh-TW`, `af-zh-TW`, …); asking yt-dlp for "all subtitles"
  downloads every one of them. Only the listed native codes are requested, matched exactly.
- **Rolling-caption de-duplication** in the VTT parser — auto-generated tracks repeat each line
  as it scrolls, so consecutive duplicates are dropped.

### Notes on the defaults
- **VAD is off by default** (`--vad` opts in), which forces the sequential Whisper path:
  `BatchedInferencePipeline` derives its clips from voice-activity detection and cannot run with
  `vad_filter=False` (it fails with `No clip timestamps found`). VAD silently drops quiet speech —
  in one measured comparison on lecture audio, turning it off captured 49% more domain terms.
  The cost is roughly 0.05x realtime instead of 0.025x. Single comparison on one audio set, not
  a benchmark.
- **`--batch-size` defaults to 4**, not 8: on an 8 GB card a batch of 8 spills into shared memory
  and drops to ~0.2x realtime — slower than not batching at all.
- **`--sleep` defaults to 1.5s** between videos, out of respect for the source's rate limits.

[0.1.0]: https://github.com/drpwchen/ytscribe/releases/tag/v0.1.0
