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
3. Transcribe with `scripts/transcribe_groq.py` when speech content is needed.
4. Extract frames with `scripts/extract_frames.sh` when visual context or screenshots are needed.
5. For Obsidian notes, read `references/obsidian-video-note.md` before writing.
6. Validate deliverables with `scripts/verify_obsidian_note.sh` and run `touch <note>` after editing an Obsidian file externally.

Example:

```bash
WORK=/tmp/video-transcribe/codex-super-app
mkdir -p "$WORK"

SKILL_DIR="$HOME/.codex/skills/video-transcribe"
# In this repo, use: SKILL_DIR=platforms/codex/skills/video-transcribe
# In Claude runtime, use: SKILL_DIR="$HOME/.claude/skills/video-transcribe"

VIDEO=$("$SKILL_DIR/scripts/download_media.sh" "$URL" "$WORK" full)

"$SKILL_DIR/scripts/transcribe_groq.py" \
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

## Bundled Resources

- `scripts/download_media.sh`: yt-dlp wrapper with cookie retry and `uvx --from yt-dlp` fallback.
- `scripts/transcribe_groq.py`: media-to-audio extraction, size-based segmentation, Groq transcription, and timestamp merge.
- `scripts/extract_frames.sh`: uniform or timestamp-based keyframe extraction.
- `scripts/verify_obsidian_note.sh`: Markdown image/timestamp/frontmatter checks.
- `references/obsidian-video-note.md`: long-form Obsidian note structure and coverage standard.
- `references/troubleshooting.md`: common yt-dlp, Groq, ffmpeg, and note-validation failures.

Load reference files only when the current request needs that detail.
