#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  extract_frames.sh VIDEO OUT_DIR [--count N] [--timestamps CSV_OR_FILE] [--scale WIDTH]

Examples:
  extract_frames.sh video.mp4 frames --count 16
  extract_frames.sh video.mp4 frames --timestamps "00:00:10,00:03:20,01:02:05"
  extract_frames.sh video.mp4 frames --timestamps timestamps.txt --scale 1440
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  usage
  exit 2
fi

video="$1"
out_dir="$2"
shift 2

count=8
timestamps=""
scale=1280

while [[ $# -gt 0 ]]; do
  case "$1" in
    --count)
      count="${2:?missing --count value}"
      shift 2
      ;;
    --timestamps)
      timestamps="${2:?missing --timestamps value}"
      shift 2
      ;;
    --scale)
      scale="${2:?missing --scale value}"
      shift 2
      ;;
    *)
      echo "[video-transcribe] unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! -s "$video" ]]; then
  echo "[video-transcribe] video not found or empty: $video" >&2
  exit 1
fi

mkdir -p "$out_dir"
find "$out_dir" -maxdepth 1 -type f -name 'frame_*.jpg' -delete 2>/dev/null || true

extract_one() {
  local ts="$1"
  local idx="$2"
  local dest
  dest=$(printf '%s/frame_%03d.jpg' "$out_dir" "$idx")
  ffmpeg -hide_banner -loglevel error -y \
    -ss "$ts" -i "$video" \
    -frames:v 1 -vf "scale=${scale}:-2" -q:v 2 "$dest"
}

idx=1
if [[ -n "$timestamps" ]]; then
  if [[ -f "$timestamps" ]]; then
    while IFS= read -r ts; do
      [[ -z "$ts" ]] && continue
      extract_one "$ts" "$idx"
      idx=$((idx + 1))
    done < "$timestamps"
  else
    IFS=',' read -r -a items <<< "$timestamps"
    for ts in "${items[@]}"; do
      ts="${ts#"${ts%%[![:space:]]*}"}"
      ts="${ts%"${ts##*[![:space:]]}"}"
      [[ -z "$ts" ]] && continue
      extract_one "$ts" "$idx"
      idx=$((idx + 1))
    done
  fi
else
  duration="$(
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$video" |
      awk '{printf "%.3f", $1}'
  )"
  if [[ -z "$duration" || "$duration" == "0.000" ]]; then
    echo "[video-transcribe] could not read video duration" >&2
    exit 1
  fi

  while [[ "$idx" -le "$count" ]]; do
    ts=$(awk -v d="$duration" -v i="$idx" -v c="$count" 'BEGIN { printf "%.3f", d * i / (c + 1) }')
    extract_one "$ts" "$idx"
    idx=$((idx + 1))
  done
fi

actual_count=$(find "$out_dir" -maxdepth 1 -type f -name 'frame_*.jpg' -size +0c | wc -l | tr -d ' ')
echo "[video-transcribe] extracted frames: $actual_count -> $out_dir" >&2
printf '%s\n' "$actual_count"
