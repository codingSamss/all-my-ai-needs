#!/usr/bin/env python3
"""Transcribe a local media file with Groq Whisper and merge timestamped output."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Any


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"[video-transcribe] missing required tool: {name}")


def ffprobe_duration(path: pathlib.Path) -> float:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise SystemExit(f"[video-transcribe] could not read duration for {path}") from exc


def hhmmss(seconds: float) -> str:
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def extract_audio(media: pathlib.Path, work_dir: pathlib.Path) -> pathlib.Path:
    audio = work_dir / "audio.m4a"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(media),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "aac",
            "-b:a",
            "48k",
            str(audio),
        ]
    )
    if not audio.exists() or audio.stat().st_size == 0:
        raise SystemExit("[video-transcribe] ffmpeg produced an empty audio file")
    return audio


def segment_audio(audio: pathlib.Path, work_dir: pathlib.Path, segment_seconds: int, max_bytes: int) -> list[pathlib.Path]:
    if audio.stat().st_size <= max_bytes:
        return [audio]

    segment_dir = work_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    for old in segment_dir.glob("segment_*.m4a"):
        old.unlink()

    pattern = segment_dir / "segment_%03d.m4a"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio),
            "-f",
            "segment",
            "-segment_time",
            str(segment_seconds),
            "-reset_timestamps",
            "1",
            "-c",
            "copy",
            str(pattern),
        ]
    )
    chunks = sorted(segment_dir.glob("segment_*.m4a"))
    if not chunks:
        raise SystemExit("[video-transcribe] audio segmentation produced no chunks")

    too_large = [p.name for p in chunks if p.stat().st_size > max_bytes]
    if too_large:
        raise SystemExit(
            "[video-transcribe] some chunks still exceed max bytes; reduce --segment-seconds: "
            + ", ".join(too_large)
        )
    return chunks


def load_prompt(args: argparse.Namespace) -> str:
    prompt_parts: list[str] = []
    if args.prompt:
        prompt_parts.append(args.prompt)
    if args.prompt_file:
        prompt_parts.append(pathlib.Path(args.prompt_file).read_text(encoding="utf-8").strip())
    return "\n".join(p for p in prompt_parts if p).strip()


def curl_transcribe(
    chunk: pathlib.Path,
    out_json: pathlib.Path,
    *,
    model: str,
    language: str | None,
    prompt: str,
    retries: int,
) -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise SystemExit("[video-transcribe] GROQ_API_KEY is not set")

    cmd = [
        "curl",
        "-sS",
        "--fail-with-body",
        "-X",
        "POST",
        "https://api.groq.com/openai/v1/audio/transcriptions",
        "-H",
        f"Authorization: Bearer {api_key}",
        "-F",
        f"file=@{chunk}",
        "-F",
        f"model={model}",
        "-F",
        "response_format=verbose_json",
        "-o",
        str(out_json),
    ]
    if language and language != "auto":
        cmd.extend(["-F", f"language={language}"])
    if prompt:
        cmd.extend(["-F", f"prompt={prompt}"])

    last_error = ""
    for attempt in range(retries + 1):
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode == 0:
            return
        last_error = (proc.stderr or proc.stdout or "").strip()
        if attempt < retries:
            time.sleep(min(20, 4 + attempt * 4))
    raise SystemExit(f"[video-transcribe] Groq transcription failed for {chunk.name}: {last_error}")


def merge_outputs(json_paths: list[pathlib.Path], offsets: list[float], work_dir: pathlib.Path) -> None:
    merged_segments: list[dict[str, Any]] = []
    plain_text_parts: list[str] = []

    for json_path, offset in zip(json_paths, offsets):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        text = (data.get("text") or "").strip()
        if text:
            plain_text_parts.append(text)

        segments = data.get("segments") or []
        if segments:
            for seg in segments:
                start = float(seg.get("start") or 0) + offset
                end = float(seg.get("end") or start) + offset
                merged_segments.append(
                    {
                        "start": start,
                        "end": end,
                        "text": (seg.get("text") or "").strip(),
                    }
                )
        elif text:
            merged_segments.append({"start": offset, "end": offset, "text": text})

    (work_dir / "transcript.txt").write_text("\n\n".join(plain_text_parts).strip() + "\n", encoding="utf-8")
    (work_dir / "transcript_segments.json").write_text(
        json.dumps(merged_segments, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = ["# Transcript", ""]
    for seg in merged_segments:
        if not seg["text"]:
            continue
        lines.append(f"- `{hhmmss(seg['start'])}` {seg['text']}")
    (work_dir / "transcript_global.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", help="local audio or video file")
    parser.add_argument("--work-dir", required=True, help="working directory for audio, chunks, and transcripts")
    parser.add_argument("--model", default="whisper-large-v3")
    parser.add_argument("--language", default="auto", help="ISO language code such as en or zh; use auto to omit")
    parser.add_argument("--prompt", default="", help="technical vocabulary/context prompt")
    parser.add_argument("--prompt-file", help="file containing technical vocabulary/context prompt")
    parser.add_argument("--segment-seconds", type=int, default=1200)
    parser.add_argument("--max-bytes", type=int, default=24_000_000)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    require_tool("ffmpeg")
    require_tool("ffprobe")
    require_tool("curl")

    media = pathlib.Path(args.media).expanduser().resolve()
    if not media.exists() or media.stat().st_size == 0:
        raise SystemExit(f"[video-transcribe] media file not found or empty: {media}")

    work_dir = pathlib.Path(args.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    prompt = load_prompt(args)
    audio = extract_audio(media, work_dir)
    chunks = segment_audio(audio, work_dir, args.segment_seconds, args.max_bytes)

    json_dir = work_dir / "groq_json"
    json_dir.mkdir(parents=True, exist_ok=True)
    json_paths: list[pathlib.Path] = []
    offsets: list[float] = []
    offset = 0.0

    for idx, chunk in enumerate(chunks):
        out_json = json_dir / f"transcript_{idx:03d}.json"
        print(f"[video-transcribe] transcribing {chunk.name} ({idx + 1}/{len(chunks)})", file=sys.stderr)
        curl_transcribe(
            chunk,
            out_json,
            model=args.model,
            language=args.language,
            prompt=prompt,
            retries=args.retries,
        )
        json_paths.append(out_json)
        offsets.append(offset)
        offset += ffprobe_duration(chunk)

    merge_outputs(json_paths, offsets, work_dir)
    print(f"[video-transcribe] transcript: {work_dir / 'transcript_global.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
