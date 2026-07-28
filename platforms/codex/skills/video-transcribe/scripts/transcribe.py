#!/usr/bin/env python3
"""Transcribe a local media file and emit timestamped, optionally speaker-tagged output.

Backends:
  groq  Groq Whisper cloud API (default; needs GROQ_API_KEY; no speaker labels)
  moss  local MOSS-Transcribe-Diarize via moss-transcribe.cpp (free, offline, diarizing,
        but saturates the GPU — see MOSS_CHUNK_SECONDS for the measured cost curve)

Artifacts written to --work-dir are identical across backends:
  transcript.txt              plain text
  transcript_segments.json    [{start, end, text, speaker?, chunk?}]
  transcript_global.md        timestamped markdown list
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Any, TypedDict


class Segment(TypedDict, total=False):
    start: float
    end: float
    text: str
    speaker: str
    chunk: int  # moss only, and only when the audio was split; speaker labels are chunk-local


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


def extract_audio(media: pathlib.Path, work_dir: pathlib.Path, *, fmt: str) -> pathlib.Path:
    """fmt='m4a' for the Groq upload path, fmt='wav16' for local MOSS inference."""
    if fmt == "wav16":
        audio = work_dir / "audio.wav"
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        audio = work_dir / "audio.m4a"
        codec_args = ["-c:a", "aac", "-b:a", "48k"]

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
            *codec_args,
            str(audio),
        ]
    )
    if not audio.exists() or audio.stat().st_size == 0:
        raise SystemExit("[video-transcribe] ffmpeg produced an empty audio file")
    return audio


# ---------------------------------------------------------------- MOSS backend

# MOSS-Transcribe-Diarize emits a compact stream of `[start][Sxx]text[end]` runs,
# e.g. `[0.48][S01]Welcome everyone[1.66][12.26][S02]The new transcription[13.50]`.
# The speaker tag is optional so single-speaker output still parses.
MOSS_SEGMENT_RE = re.compile(
    r"\[(?P<start>\d+(?:\.\d+)?)\]"
    r"(?:\[(?P<speaker>S\d+)\])?"
    r"(?P<text>.*?)"
    r"\[(?P<end>\d+(?:\.\d+)?)\]",
    re.DOTALL,
)


def parse_moss_stream(raw: str) -> list[Segment]:
    segments: list[Segment] = []
    for match in MOSS_SEGMENT_RE.finditer(raw):
        text = match.group("text").strip()
        if not text:
            continue
        segment: Segment = {
            "start": float(match.group("start")),
            "end": float(match.group("end")),
            "text": text,
        }
        speaker = match.group("speaker")
        if speaker:
            segment["speaker"] = speaker
        segments.append(segment)
    return segments


def resolve_moss_bin(explicit: str | None) -> str:
    candidates = [
        explicit,
        os.environ.get("MOSS_TRANSCRIBE_BIN"),
        shutil.which("moss-transcribe"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        # resolve(), not expanduser(): a bare relative name would otherwise be
        # handed to subprocess as a PATH lookup and fail.
        path = pathlib.Path(candidate).expanduser().resolve()
        if path.exists():
            return str(path)
    raise SystemExit(
        "[video-transcribe] moss-transcribe binary not found.\n"
        "  Set --moss-bin or MOSS_TRANSCRIBE_BIN, or put moss-transcribe on PATH.\n"
        "  Build: https://github.com/localai-org/moss-transcribe.cpp"
    )


def resolve_moss_model(explicit: str | None) -> str:
    candidate = explicit or os.environ.get("MOSS_TRANSCRIBE_MODEL")
    if not candidate:
        raise SystemExit(
            "[video-transcribe] MOSS model not set.\n"
            "  Set --moss-model or MOSS_TRANSCRIBE_MODEL to a .gguf file.\n"
            "  Prebuilt weights: https://huggingface.co/mudler/moss-transcribe.cpp-gguf"
        )
    path = pathlib.Path(candidate).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"[video-transcribe] MOSS model file not found: {path}")
    return str(path)


# Measured on an M3 Max (Metal, q5_k) — cost is superlinear in clip length
# because attention over the encoder sequence is O(N^2):
#   180 s -> 47 s   (RTF 0.26)
#   300 s -> 156 s  (RTF 0.52)
#   600 s -> 967 s  (RTF 1.61, i.e. slower than real time)
#   1487 s -> fails, Metal tries to allocate a 23.5 GiB buffer
# Chunking is therefore mandatory, and short chunks are strictly faster overall.
MOSS_CHUNK_SECONDS = 180


def split_wav_by_duration(
    audio: pathlib.Path, work_dir: pathlib.Path, chunk_seconds: int
) -> list[tuple[pathlib.Path, float]]:
    """Split into fixed-length wav chunks. Returns [(path, start_offset_seconds)]."""
    duration = ffprobe_duration(audio)
    if duration <= chunk_seconds:
        return [(audio, 0.0)]

    chunk_dir = work_dir / "moss_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for old in chunk_dir.glob("chunk_*.wav"):
        old.unlink()

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
            str(chunk_seconds),
            "-c",
            "copy",
            str(chunk_dir / "chunk_%03d.wav"),
        ]
    )
    chunks = sorted(chunk_dir.glob("chunk_*.wav"))
    if not chunks:
        raise SystemExit("[video-transcribe] ffmpeg produced no chunks")

    offsets: list[tuple[pathlib.Path, float]] = []
    running = 0.0
    for chunk in chunks:
        offsets.append((chunk, running))
        running += ffprobe_duration(chunk)
    return offsets


def run_moss_once(
    binary: str,
    model: str,
    audio: pathlib.Path,
    raw_path: pathlib.Path,
    *,
    max_new: int,
    env: dict[str, str],
) -> list[Segment]:
    cmd = [binary, "transcribe", model, str(audio), "--max-new", str(max_new)]
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env)
    raw_path.write_text(proc.stdout or "", encoding="utf-8")

    segments = parse_moss_stream(proc.stdout or "")
    if segments:
        # moss-transcribe trips a cleanup assertion on the Metal backend
        # (ggml-metal-device.m: GGML_ASSERT([rsets->data count] == 0)) and so exits
        # non-zero on every successful run. The transcript is already on stdout by
        # then, so parseable output — not the exit code — is the success signal.
        return segments

    detail = (proc.stderr or proc.stdout or "").strip()
    if "failed to allocate buffer" in detail:
        raise SystemExit(
            f"[video-transcribe] moss ran out of GPU memory on a {hhmmss(ffprobe_duration(audio))} chunk.\n"
            f"  Lower --moss-chunk-seconds (current chunking still produced too long a clip).\n"
            f"  {detail.splitlines()[-1] if detail else ''}"
        )
    raise SystemExit(
        "[video-transcribe] moss-transcribe produced no parseable segments.\n"
        f"  Raw output kept at: {raw_path}\n"
        f"  exit code: {proc.returncode}\n"
        "  If the output format changed, update MOSS_SEGMENT_RE in this script.\n"
        f"  {detail[-400:] if detail else ''}"
    )


def transcribe_moss(
    media: pathlib.Path,
    work_dir: pathlib.Path,
    *,
    moss_bin: str | None,
    moss_model: str | None,
    max_new: int,
    threads: int | None,
    chunk_seconds: int = MOSS_CHUNK_SECONDS,
) -> list[Segment]:
    binary = resolve_moss_bin(moss_bin)
    model = resolve_moss_model(moss_model)
    audio = extract_audio(media, work_dir, fmt="wav16")

    raw_dir = work_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if threads:
        env["MTD_THREADS"] = str(threads)

    duration = ffprobe_duration(audio)
    chunks = split_wav_by_duration(audio, work_dir, chunk_seconds)
    print(
        f"[video-transcribe] moss: transcribing {hhmmss(duration)} of audio "
        f"in {len(chunks)} chunk(s) of up to {chunk_seconds}s",
        file=sys.stderr,
    )
    if len(chunks) > 1:
        print(
            "[video-transcribe] moss: speaker labels are assigned per chunk in order of "
            "appearance, so S01 in one chunk is NOT guaranteed to be the same person as "
            "S01 in another. Treat labels as chunk-local.",
            file=sys.stderr,
        )

    segments: list[Segment] = []
    for index, (chunk, offset) in enumerate(chunks):
        raw_path = raw_dir / f"moss_stream_{index:03d}.txt"
        part = run_moss_once(
            binary, model, chunk, raw_path, max_new=max_new, env=env
        )
        for seg in part:
            seg["start"] += offset
            seg["end"] += offset
            if len(chunks) > 1:
                seg["chunk"] = index
        segments.extend(part)
        print(
            f"[video-transcribe] moss: chunk {index + 1}/{len(chunks)} -> {len(part)} segments",
            file=sys.stderr,
        )

    return segments


# ---------------------------------------------------------------- Groq backend


def segment_audio(
    audio: pathlib.Path, work_dir: pathlib.Path, segment_seconds: int, max_bytes: int
) -> list[pathlib.Path]:
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


def transcribe_groq(
    media: pathlib.Path,
    work_dir: pathlib.Path,
    *,
    model: str,
    language: str,
    prompt: str,
    segment_seconds: int,
    max_bytes: int,
    retries: int,
) -> list[Segment]:
    require_tool("curl")
    audio = extract_audio(media, work_dir, fmt="m4a")
    chunks = segment_audio(audio, work_dir, segment_seconds, max_bytes)

    raw_dir = work_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    segments: list[Segment] = []
    offset = 0.0
    for idx, chunk in enumerate(chunks):
        out_json = raw_dir / f"groq_{idx:03d}.json"
        print(
            f"[video-transcribe] groq: transcribing {chunk.name} ({idx + 1}/{len(chunks)})",
            file=sys.stderr,
        )
        curl_transcribe(
            chunk,
            out_json,
            model=model,
            language=language,
            prompt=prompt,
            retries=retries,
        )

        data: dict[str, Any] = json.loads(out_json.read_text(encoding="utf-8"))
        chunk_segments = data.get("segments") or []
        if chunk_segments:
            for seg in chunk_segments:
                start = float(seg.get("start") or 0) + offset
                end = float(seg.get("end") or start) + offset
                text = (seg.get("text") or "").strip()
                if text:
                    segments.append({"start": start, "end": end, "text": text})
        else:
            text = (data.get("text") or "").strip()
            if text:
                segments.append({"start": offset, "end": offset, "text": text})

        offset += ffprobe_duration(chunk)

    if not segments:
        raise SystemExit("[video-transcribe] Groq returned no transcript segments")
    return segments


# ----------------------------------------------------------------- output side


def write_outputs(segments: list[Segment], work_dir: pathlib.Path) -> None:
    (work_dir / "transcript.txt").write_text(
        "\n".join(seg["text"] for seg in segments).strip() + "\n", encoding="utf-8"
    )
    (work_dir / "transcript_segments.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    has_speakers = any(seg.get("speaker") for seg in segments)
    lines = ["# Transcript", ""]
    for seg in segments:
        stamp = f"`{hhmmss(seg['start'])}`"
        if has_speakers:
            speaker = seg.get("speaker", "S??")
            lines.append(f"- {stamp} **{speaker}** {seg['text']}")
        else:
            lines.append(f"- {stamp} {seg['text']}")
    (work_dir / "transcript_global.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_prompt(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.prompt:
        parts.append(args.prompt)
    if args.prompt_file:
        parts.append(pathlib.Path(args.prompt_file).read_text(encoding="utf-8").strip())
    return "\n".join(p for p in parts if p).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("media", help="local audio or video file")
    parser.add_argument("--work-dir", required=True, help="working directory for audio and transcripts")
    parser.add_argument(
        "--backend",
        choices=["moss", "groq"],
        default="groq",
        help=(
            "groq = cloud, fast, no speaker labels, needs GROQ_API_KEY (default); "
            "moss = local, free, offline, speaker-tagged, but saturates the GPU "
            "(roughly a quarter of the audio duration in wall clock on an M3 Max)"
        ),
    )
    parser.add_argument("--language", default="auto", help="ISO code such as en or zh; auto to omit (groq only)")
    parser.add_argument("--prompt", default="", help="technical vocabulary/context prompt (groq only)")
    parser.add_argument("--prompt-file", help="file containing the vocabulary/context prompt (groq only)")

    moss_group = parser.add_argument_group("moss backend")
    moss_group.add_argument("--moss-bin", help="path to moss-transcribe (or set MOSS_TRANSCRIBE_BIN)")
    moss_group.add_argument("--moss-model", help="path to .gguf weights (or set MOSS_TRANSCRIBE_MODEL)")
    moss_group.add_argument("--max-new", type=int, default=65536, help="token budget; keep high for long audio")
    moss_group.add_argument("--threads", type=int, help="inference threads (sets MTD_THREADS; 8 is a good default)")
    moss_group.add_argument(
        "--moss-chunk-seconds",
        type=int,
        default=MOSS_CHUNK_SECONDS,
        help=(
            f"split audio into chunks of this length before inference (default {MOSS_CHUNK_SECONDS}). "
            "Cost is superlinear in clip length; longer chunks are slower overall and can exhaust GPU memory."
        ),
    )

    groq_group = parser.add_argument_group("groq backend")
    groq_group.add_argument("--model", default="whisper-large-v3")
    groq_group.add_argument("--segment-seconds", type=int, default=1200)
    groq_group.add_argument("--max-bytes", type=int, default=24_000_000)
    groq_group.add_argument("--retries", type=int, default=2)

    args = parser.parse_args()

    require_tool("ffmpeg")
    require_tool("ffprobe")

    media = pathlib.Path(args.media).expanduser().resolve()
    if not media.exists() or media.stat().st_size == 0:
        raise SystemExit(f"[video-transcribe] media file not found or empty: {media}")

    work_dir = pathlib.Path(args.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.backend == "moss":
        segments = transcribe_moss(
            media,
            work_dir,
            moss_bin=args.moss_bin,
            moss_model=args.moss_model,
            max_new=args.max_new,
            threads=args.threads,
            chunk_seconds=args.moss_chunk_seconds,
        )
    else:
        segments = transcribe_groq(
            media,
            work_dir,
            model=args.model,
            language=args.language,
            prompt=load_prompt(args),
            segment_seconds=args.segment_seconds,
            max_bytes=args.max_bytes,
            retries=args.retries,
        )

    write_outputs(segments, work_dir)
    speakers = sorted({seg["speaker"] for seg in segments if seg.get("speaker")})
    summary = f"{len(segments)} segments"
    if speakers:
        summary += f", {len(speakers)} speakers ({', '.join(speakers)})"
    print(f"[video-transcribe] {args.backend}: {summary}", file=sys.stderr)
    print(f"[video-transcribe] transcript: {work_dir / 'transcript_global.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
