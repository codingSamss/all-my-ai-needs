#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  verify_obsidian_note.sh NOTE.md ASSETS_DIR [TIMESTAMPS_FILE]

Checks frontmatter, Markdown image references, asset existence, and optional timestamp coverage.
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

note="$1"
assets_dir="$2"
timestamps_file="${3:-}"

if [[ ! -s "$note" ]]; then
  echo "[video-transcribe] note missing or empty: $note" >&2
  exit 1
fi

if [[ ! -d "$assets_dir" ]]; then
  echo "[video-transcribe] assets directory missing: $assets_dir" >&2
  exit 1
fi

note_dir="$(cd "$(dirname "$note")" && pwd)"
asset_count=$(find "$assets_dir" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -size +0c | wc -l | tr -d ' ')
ref_file=$(mktemp)
trap 'rm -f "$ref_file"' EXIT

grep -oE '!\[[^]]*\]\([^)]+\)' "$note" |
  sed -E 's/^!\[[^]]*\]\(([^)]+)\)$/\1/' > "$ref_file" || true

ref_count=$(wc -l < "$ref_file" | tr -d ' ')
missing_refs=0
while IFS= read -r ref; do
  [[ -z "$ref" ]] && continue
  [[ "$ref" =~ ^https?:// ]] && continue
  ref="${ref%%#*}"
  ref="${ref%%\?*}"
  if [[ "$ref" = /* ]]; then
    candidate="$ref"
  else
    candidate="$note_dir/$ref"
  fi
  if [[ ! -s "$candidate" ]]; then
    echo "[video-transcribe] missing image reference: $ref" >&2
    missing_refs=$((missing_refs + 1))
  fi
done < "$ref_file"

frontmatter_delimiters=$(awk 'NR==1 && $0=="---" {count++} NR>1 && $0=="---" {count++; exit} END {print count+0}' "$note")
if [[ "$frontmatter_delimiters" -lt 2 ]]; then
  echo "[video-transcribe] frontmatter delimiters not found at top of note" >&2
  exit 1
fi

missing_timestamps=0
if [[ -n "$timestamps_file" ]]; then
  if [[ ! -s "$timestamps_file" ]]; then
    echo "[video-transcribe] timestamps file missing or empty: $timestamps_file" >&2
    exit 1
  fi
  while IFS= read -r ts; do
    [[ -z "$ts" ]] && continue
    if ! grep -Fq "$ts" "$note"; then
      echo "[video-transcribe] missing timestamp in note: $ts" >&2
      missing_timestamps=$((missing_timestamps + 1))
    fi
  done < "$timestamps_file"
fi

echo "[video-transcribe] asset files: $asset_count"
echo "[video-transcribe] markdown image refs: $ref_count"
echo "[video-transcribe] missing refs: $missing_refs"
echo "[video-transcribe] missing timestamps: $missing_timestamps"

if [[ "$missing_refs" -gt 0 || "$missing_timestamps" -gt 0 ]]; then
  exit 1
fi
