#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  download_media.sh URL WORK_DIR [audio|video|full]

Downloads media with yt-dlp. Logs go to stderr; final local media path is printed to stdout.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 || $# -gt 3 ]]; then
  usage
  exit 2
fi

url="$1"
work_dir="$2"
mode="${3:-full}"

mkdir -p "$work_dir"

if command -v yt-dlp >/dev/null 2>&1; then
  ytdlp=(yt-dlp)
elif command -v uvx >/dev/null 2>&1; then
  ytdlp=(uvx --from yt-dlp yt-dlp)
else
  echo "[video-transcribe] yt-dlp not found. Install with: brew install yt-dlp" >&2
  exit 1
fi

common=(
  --no-playlist
  --restrict-filenames
  --newline
  -o "$work_dir/source.%(ext)s"
)

case "$mode" in
  audio)
    format_args=(-x --audio-format m4a --audio-quality 5)
    ;;
  video|full)
    format_args=(-f "bestvideo[height<=720]+bestaudio/best[height<=720]/best" --merge-output-format mp4)
    ;;
  *)
    echo "[video-transcribe] unknown mode: $mode (expected audio, video, or full)" >&2
    exit 2
    ;;
esac

run_download() {
  local with_cookies="$1"
  if [[ "$with_cookies" == "1" ]]; then
    "${ytdlp[@]}" "${common[@]}" --cookies-from-browser chrome "${format_args[@]}" "$url"
  else
    "${ytdlp[@]}" "${common[@]}" "${format_args[@]}" "$url"
  fi
}

echo "[video-transcribe] downloading ($mode): $url" >&2
if ! run_download 1 >&2; then
  echo "[video-transcribe] cookie-based download failed; retrying without browser cookies" >&2
  run_download 0 >&2
fi

media_path="$(
  find "$work_dir" -maxdepth 1 -type f \
    ! -name '*.part' \
    ! -name '*.ytdl' \
    \( -iname 'source.*' -o -iname '*.mp4' -o -iname '*.m4a' -o -iname '*.mp3' -o -iname '*.webm' \) \
    -print | sort | tail -n 1
)"

if [[ -z "$media_path" || ! -s "$media_path" ]]; then
  echo "[video-transcribe] download finished but no non-empty media file was found in $work_dir" >&2
  exit 1
fi

printf '%s\n' "$media_path"
