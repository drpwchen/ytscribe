# ytscribe

Fetch transcripts for an entire YouTube channel, cheaply.

Subtitles first — most channels already have them, and downloading a subtitle
track costs a few kilobytes and no compute. Only when a video has no track at
all does it fall back to local Whisper on your GPU. Nothing is sent to a cloud
API, and no video file is ever downloaded or kept.

Built to feed transcripts into an LLM *later*, without spending tokens on the
fetching itself.

## Quickstart

```bash
git clone https://github.com/drpwchen/yt-transcript-kit && cd yt-transcript-kit
pip install -e .

# Subtitles only
ytscribe https://www.youtube.com/@somechannel -o transcripts

# Subtitles, plus local Whisper for videos that have none
ytscribe https://www.youtube.com/@somechannel -o transcripts --whisper
```

You should see `[1/2] Listing videos…`, then one line per video (`sub` for a subtitle
track, `ASR` for Whisper, `---` for a video with neither), and a closing
`Done: N from subtitles, M via Whisper, K already present`.

> 🧋 Saved you some time? [Buy me a drink](https://drpwchen.com/en/support/).

Output is one Markdown file per video, with YAML frontmatter:

```markdown
---
title: "How to do the thing"
video_id: "abc123"
url: "https://www.youtube.com/watch?v=abc123"
duration_sec: 955
sub_lang: "en"
source: "youtube-subtitles"
---

Text of the transcript, one caption line per line...
```

`source` is always either `youtube-subtitles` or `whisper:<model>`, so you can
tell human-written captions from machine output downstream. Re-running skips
videos already on disk, which makes this usable as an incremental sync.

## Install

```bash
pip install -e .          # subtitles only
pip install -e ".[asr]"   # plus local Whisper
```

Needs [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) on PATH (`pip install yt-dlp`).
The `asr` extra pulls in `faster-whisper`, which needs a CUDA-capable GPU to be
worth using, plus `ffmpeg` on PATH.

## Requirements and cost

- Python 3.10+, any OS. [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) is installed as a dependency.
- Subtitles-only mode: no GPU, no account, no API key. Free.
- `--whisper` mode: the `asr` extra (`faster-whisper`), `ffmpeg` on PATH, and a CUDA GPU
  (the default is `--device cuda`). The model is downloaded once from Hugging Face. Still free, no API key.

## Limitations

- A video with no subtitle track and no `--whisper` gets no transcript; it is listed at the end of the run.
- Subtitles are whatever the uploader or YouTube's auto-captioning produced; they are not corrected.
- `--whisper` temporarily downloads each video's audio (deleted afterwards unless `--keep-audio`).
- It relies on `yt-dlp`, so a YouTube-side change can break fetching until `yt-dlp` is updated.
- A video that fails is reported and skipped; the batch continues.

## Things that will bite you

These are all things this tool already handles, documented so you know *why*
the defaults are what they are.

**YouTube exposes hundreds of fake subtitle tracks.** A video with Chinese
captions also advertises `ab-zh-TW` (Abkhazian from Chinese), `af-zh-TW`, and
~200 more machine translations. Asking for "all subtitles" downloads all of
them. `--langs` lists native codes only, and yt-dlp matches them exactly.

**Batched Whisper forces VAD on.** `BatchedInferencePipeline` derives its clips
from voice-activity detection, so it cannot run with `vad_filter=False` — it
fails with `No clip timestamps found`. That matters because VAD silently drops
quiet speech. In one measured comparison on lecture audio, turning VAD off
captured 49% more domain terms. So the default here is the sequential path with
VAD off: roughly 0.05x realtime instead of 0.025x, and worth it. Pass
`--vad` if you want speed and your audio is clean and loud.

**`--batch-size 8` overflows an 8 GB card.** It spills into shared memory and
drops to ~0.2x realtime — slower than not batching at all. Default is 4.

**Rolling captions duplicate every line.** Auto-generated VTT repeats each line
as it scrolls. The parser drops consecutive duplicates.

**A slow ASR run usually means GPU contention, not a slow model.** Check
`nvidia-smi` before concluding anything about model speed. A clip that took 318
seconds once re-ran in 24 seconds on an idle GPU.

## Options

| Flag | Default | Notes |
|---|---|---|
| `-o, --out` | `transcripts` | Output directory |
| `--langs` | `zh-TW,zh-Hant,zh,ja,ko,en,en-US` | Native tracks, priority order |
| `--whisper` | off | Local ASR fallback for videos with no subtitles |
| `--model` | `large-v3` | Model name, or a local CTranslate2 directory |
| `--batch-size` | `4` | Keep at 4 on 8 GB |
| `--beam-size` | `3` | 5 for a bit more quality |
| `--vad` | off | Enables batched mode; faster, drops quiet speech |
| `--language` | auto | Force a code, e.g. `zh` |
| `--only` | all | Comma-separated video IDs |
| `--keep-audio` | off | Audio is deleted after transcription by default |
| `--sleep` | `1.5` | Seconds between videos |

Any model `faster-whisper` accepts works, including fine-tunes. For
code-switched Mandarin/English, a local
[Breeze-ASR-25](https://huggingface.co/MediaTek-Research/Breeze-ASR-25)
conversion measurably beats `large-v3`; point `--model` at the directory.

## Related

[**asr-benchmark**](https://github.com/drpwchen/asr-benchmark) — score ASR models
on your own audio without ground-truth transcripts. If you are using the
`--whisper` path here and want to know which model actually transcribes your
domain best, that is the tool that answers it. The VAD and batch-size defaults
documented above came out of exactly that kind of measurement.

## Please use this responsibly

Transcripts are the creator's work. Fetching them for your own reading, search,
or study is one thing; republishing them, or passing them off as your own
content, is another. Check the channel's terms before doing anything public
with the output, and respect the rate limits — `--sleep` exists for a reason.

## License

MIT

---

## 🌱 Start here if you're new to AI agents ／ AI agent 新手起點

This tool is one piece of my personal AI workflow. If you want to learn how to use AI agents like Claude Code from zero (no programming background needed), I wrote a beginner series (in Traditional Chinese):

這個工具是我個人 AI 工作流的一部分。想從零開始學怎麼用 Claude Code 這類 AI agent（不需要程式背景），可以從我的入門系列開始：

1. [從零開始：安裝、看懂 GitHub、跑起你的第一個工具](https://drpwchen.com/posts/getting-started/)
2. [怎麼跟 AI agent 講話：心法、元技能與規則檔](https://drpwchen.com/posts/talking-to-agents/)
3. [自動化流程不是設計出來的，是長出來的](https://drpwchen.com/posts/growing-your-workflow/)

Full map of my tools and posts ／ 所有工具與文章的全貌 → [drpwchen.com/map](https://drpwchen.com/map/)

## Support 支持

覺得這個工具有幫助嗎？歡迎[請我喝飲料](https://drpwchen.com/support/) 🧋
If this tool helped you, you can [buy me a drink](https://drpwchen.com/en/support/).
