---
name: video-transcribe
description: "Video/audio transcription, visual frame analysis, Groq Whisper long-form transcripts, timestamped Obsidian notes, and keyframe-based visual summaries. Use for video links, audio links, 字幕/转录/视频总结/画面分析/图文笔记, especially when the result must replace watching the video. Keywords: video, transcribe, 转录, 视频, 音频, audio, subtitle, 字幕, summary, 总结, 图文笔记, 视频内容, 画面分析, visual analysis, keyframe, whisper, groq, yt-dlp"
---

# Video Transcribe

Use this skill when the user asks to understand, transcribe, summarize, or visually analyze a video/audio source.

## Mode Selection

- **Full note / no omission**: user says 全量、完整、不要看视频、替代看视频、图文笔记, or asks about completeness. Download the source, transcribe the whole audio, extract frames, and produce a coverage-checked note.
- **Audio transcript**: user explicitly asks for 字幕、转录、他说了什么、transcribe. Produce a timestamped transcript or transcript-backed summary.
- **Visual analysis**: user explicitly asks about 画面、截图、视觉、展示了什么. Extract frames and analyze visuals; skip Groq unless speech content matters.
- **Quick summary**: user only wants a brief answer. Summarize, but still state whether the result is transcript-backed, frame-backed, or both.

When intent is unclear, default to transcript + keyframes for short videos and ask before spending API quota on long videos.

## Core Rules

- For long-form technical content, prefer Groq `whisper-large-v3` with `response_format=verbose_json`; do not use plain `text` when timestamps or completeness checks matter.
- Do not force `language=zh` for non-Chinese videos. Use the detected language or set `--language en` for English technical videos.
- Use a terminology prompt for product/tool names such as `Codex`, `Remotion`, `Supabase`, `Typefully`, `TestFlight`, `Vercel`, `Claude Code`.
- Source timestamps are an outline, not proof. Verify every listed timestamp has transcript coverage before claiming the note can replace watching the video.
- Do not add a personal status tag like `已读`; that belongs to the user, not the agent.
- Keep full transcripts in the working directory unless the user asks to store them in the note. The published note should contain structured coverage, excerpts/paraphrase, screenshots, and validation notes.

## Standard Workflow

1. Create a work directory under `/tmp/video-transcribe/<slug>`.
2. Download media with `scripts/download_media.sh`.
3. Transcribe with `scripts/transcribe.py` when speech content is needed (defaults to the Groq backend; add `--backend moss` only when speaker labels are required — see "Speaker labels" below).
4. Extract frames with `scripts/extract_frames.sh` when visual context or screenshots are needed.
5. For Obsidian notes, read `references/obsidian-video-note.md` before writing.
6. Validate deliverables with `scripts/verify_obsidian_note.sh` and run `touch <note>` after editing an Obsidian file externally.

Example:

```bash
WORK=/tmp/video-transcribe/codex-super-app
mkdir -p "$WORK"

SKILL_DIR="$HOME/.codex/skills/video-transcribe"
# In this repo, use: SKILL_DIR=platforms/codex/skills/video-transcribe
# In Codex runtime, use: SKILL_DIR="$HOME/.codex/skills/video-transcribe"

VIDEO=$("$SKILL_DIR/scripts/download_media.sh" "$URL" "$WORK" full)

"$SKILL_DIR/scripts/transcribe.py" \
  "$VIDEO" \
  --work-dir "$WORK" \
  --language en \
  --prompt "Technical terms: Codex, Remotion, Supabase, Typefully, TestFlight, Vercel, Claude Code."

"$SKILL_DIR/scripts/extract_frames.sh" \
  "$VIDEO" "$WORK/frames" --count 16
```

## Output Standards

For a note intended to replace watching a video, use two layers:

- **Readable layer**: a short executive summary, key claims, reusable playbook, decisions, tools, gotchas, and screenshots.
- **Coverage layer**: collapsible timestamp groups or phase tables that map every source timestamp to the transcript-backed note.

Avoid a single flat list of dozens of timestamps. It is technically complete but hard to read.

## Speaker labels (`--backend moss`)

Only reach for the moss backend when the material is multi-speaker (interview, podcast, two-host talk) and knowing *who said what* actually changes the note. Otherwise stay on Groq.

Setup (one-time):

```bash
export MOSS_TRANSCRIBE_BIN="$HOME/tools/moss-transcribe.cpp/build/moss-transcribe"
export MOSS_TRANSCRIBE_MODEL="$HOME/tools/moss-models/moss-transcribe-q5_k.gguf"
```

Build from https://github.com/localai-org/moss-transcribe.cpp (`cmake -B build -DMT_GGML_METAL=ON && cmake --build build -j`); weights from https://huggingface.co/mudler/moss-transcribe.cpp-gguf.

```bash
"$SKILL_DIR/scripts/transcribe.py" "$VIDEO" --work-dir "$WORK" --backend moss
```

What to expect, measured on an M3 Max (Metal, q5_k):

| Audio | Wall clock | Note |
| --- | --- | --- |
| 26 s | 2 s | |
| 180 s | 47 s | chunk size used by default |
| 450 s | 103 s | 3 chunks, timestamps merge correctly |
| 600 s **unchunked** | 967 s | slower than real time — never disable chunking |
| 1487 s **unchunked** | fails | Metal tries to allocate 23.5 GiB |

Cost is superlinear in clip length, so the script always chunks at 180 s (`--moss-chunk-seconds`). Expect the GPU to sit at ~100% and the fans to spin up for roughly a quarter of the audio duration.

Two things to know before trusting the output:

- **Speaker labels are chunk-local.** MOSS assigns `S01`, `S02` … in order of appearance *within each chunk*, so `S01` in chunk 0 is not guaranteed to be the same person as `S01` in chunk 2. `transcript_segments.json` carries a `chunk` field whenever the audio was split. Reconcile identities from context before naming speakers in a note.
- **moss-transcribe exits non-zero on every successful run** on the Metal backend (a cleanup assertion in ggml). The script treats parseable stdout as the success signal and ignores the exit code; do not "fix" that by reinstating a returncode check.
- **Chunk boundaries cut on wall-clock time, not on speech.** Splitting uses `ffmpeg -f segment -segment_time` with a stream copy, so a sentence spanning a boundary is torn in two and each half is transcribed without the other's context. Expect a garbled or truncated line at every boundary (one per 180 s of audio). If a boundary lands badly, re-run that stretch on its own with a different `--moss-chunk-seconds` to shift the cut. Splitting on silence (via `silencedetect`) would fix this properly and is not implemented yet.

## Bundled Resources

- `scripts/download_media.sh`: yt-dlp wrapper with cookie retry and `uvx --from yt-dlp` fallback.
- `scripts/transcribe.py`: media-to-audio extraction, segmentation, transcription, and timestamp merge. Two backends behind one artifact contract — `--backend groq` (default) and `--backend moss`.
- `scripts/transcribe_groq.py`: the original Groq-only script, kept for compatibility; `transcribe.py --backend groq` supersedes it.
- `scripts/extract_frames.sh`: uniform or timestamp-based keyframe extraction.
- `scripts/verify_obsidian_note.sh`: Markdown image/timestamp/frontmatter checks.
- `references/obsidian-video-note.md`: long-form Obsidian note structure and coverage standard.
- `references/troubleshooting.md`: common yt-dlp, Groq, ffmpeg, and note-validation failures.

Load reference files only when the current request needs that detail.
