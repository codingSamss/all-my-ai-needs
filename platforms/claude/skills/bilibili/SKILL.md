---
name: bilibili
description: "Read Bilibili (B站) content. Actions: search videos, view hot/rank feeds, read video details, prepare audio, and read subtitles through OpenCLI. Keywords: bilibili, b站, 哔哩哔哩, BV, 视频, 字幕, 热门, 排行."
---

# Bilibili Skill (Read-Only)

Use this skill for Bilibili search, video metadata, hot/rank feeds, and subtitle lookup. Do not use `yt-dlp` as the default Bilibili reader; Bilibili commonly blocks that route.

## When To Use

Triggered by:
- "B站搜索 [query]", "bilibili search [query]"
- "读 B站视频", "show BV..."
- "B站热门", "B站排行"
- "B站字幕", "bilibili subtitle"
- "下载 B站音频用于转录"

## Preferred Tools

1. `bili-cli` for search, hot/rank, video detail, and audio.
2. Bilibili web search API as a no-install search fallback.
3. OpenCLI for subtitles and browser-session enhanced reads.
4. `video-transcribe` for full transcript, screenshots, keyframes, or notes that replace watching the video.

## Commands

Search videos:

```bash
bili search "<query>" --type video -n 5
```

Hot and ranking:

```bash
bili hot -n 10
bili rank -n 10
```

Video details:

```bash
bili video "<BV_ID>"
```

Audio for transcription:

```bash
bili audio "<BV_ID>"
```

Subtitles through OpenCLI:

```bash
opencli bilibili subtitle "<BV_ID>"
```

No-install search fallback:

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
curl -s -A "$UA" \
  "https://api.bilibili.com/x/web-interface/search/all/v2?keyword=<QUERY>&page=1"
```

## Boundaries

- Read-only only.
- Do not use `yt-dlp` as the default Bilibili extraction route.
- For complete video understanding, transcription, visual frame analysis, or Obsidian notes, switch to `video-transcribe`.
- If `bili-cli` is missing, use the search API only for search and report that full Bilibili support needs `bili-cli`.
