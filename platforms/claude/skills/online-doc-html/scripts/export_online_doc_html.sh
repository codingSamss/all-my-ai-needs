#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  export_online_doc_html.sh [--out DIR] <markdown.md> [more.md ...]

Exports Markdown files to standalone, paste-friendly HTML for online document editors.
SVG image references are converted to PNG before embedding.
EOF
}

OUT_DIR="build/online-doc-html"
MD_FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      if [[ $# -lt 2 ]]; then
        echo "--out requires a directory" >&2
        exit 1
      fi
      OUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        MD_FILES+=("$1")
        shift
      done
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      MD_FILES+=("$1")
      shift
      ;;
  esac
done

if [[ ${#MD_FILES[@]} -eq 0 ]]; then
  usage >&2
  exit 1
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "pandoc is required. Install it first, for example: brew install pandoc" >&2
  exit 1
fi

OUT_DIR="$(mkdir -p "$OUT_DIR" && cd "$OUT_DIR" && pwd)"
PREPARED_DIR="$OUT_DIR/prepared"
ASSETS_DIR="$PREPARED_DIR/assets"
CSS_FILE="$OUT_DIR/online-doc-copy.css"
TARGETS_FILE="$OUT_DIR/targets.tsv"

rm -rf "$PREPARED_DIR"
mkdir -p "$ASSETS_DIR"
rm -f "$OUT_DIR"/*.docx

cat >"$CSS_FILE" <<'CSS'
body {
  color: #202124;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 14px;
  line-height: 1.72;
  max-width: 980px;
  margin: 32px auto;
  padding: 0 28px 56px;
}
h1 { font-size: 28px; margin: 0 0 24px; }
h2 { font-size: 22px; margin: 30px 0 14px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }
h3 { font-size: 18px; margin: 24px 0 10px; }
p { margin: 10px 0; }
table { border-collapse: collapse; width: 100%; margin: 14px 0 18px; table-layout: auto; }
th, td { border: 1px solid #d8dee4; padding: 7px 9px; vertical-align: top; }
th { background: #f6f8fa; font-weight: 600; }
pre {
  background: #f6f8fa;
  border: 1px solid #d8dee4;
  border-radius: 6px;
  overflow: auto;
  padding: 12px 14px;
}
code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
}
p > code, li > code, td > code {
  background: #f6f8fa;
  border-radius: 4px;
  padding: 1px 4px;
}
img { max-width: 100%; height: auto; display: block; margin: 14px auto; }
blockquote { border-left: 4px solid #d8dee4; color: #57606a; margin: 14px 0; padding: 2px 14px; }
CSS

printf "local_markdown\thtml\n" >"$TARGETS_FILE"

for md_file in "${MD_FILES[@]}"; do
  if [[ ! -f "$md_file" ]]; then
    echo "missing source: $md_file" >&2
    exit 1
  fi

  src="$(cd "$(dirname "$md_file")" && pwd)/$(basename "$md_file")"
  src_dir="$(dirname "$src")"
  base="$(basename "$md_file" .md)"
  prepared_md="$PREPARED_DIR/$base.md"
  html="$OUT_DIR/$base.html"

  cp "$src" "$prepared_md"

  while IFS= read -r image_ref; do
    svg_path="$(cd "$src_dir" && realpath "$image_ref")"
    png_name="$base-$(basename "${image_ref%.svg}").png"
    png_path="$ASSETS_DIR/$png_name"
    png_ref="assets/$png_name"

    if ! command -v rsvg-convert >/dev/null 2>&1; then
      echo "rsvg-convert is required for SVG diagrams. Install it first, for example: brew install librsvg" >&2
      exit 1
    fi

    rsvg-convert -f png -o "$png_path" "$svg_path"
    REF="$image_ref" REP="$png_ref" perl -0pi -e 's/\Q$ENV{REF}\E/$ENV{REP}/g' "$prepared_md"
  done < <(perl -nE 'while (/!\[[^\]]*\]\(([^)\s]+\.svg)\)/g) { say $1 }' "$src" | sort -u)

  pandoc "$prepared_md" \
    --from=gfm+pipe_tables+raw_html \
    --to=html5 \
    --standalone \
    --embed-resources \
    --resource-path="$PREPARED_DIR:$src_dir:$(pwd)" \
    --metadata "title=$base" \
    --css "$CSS_FILE" \
    --output "$html"

  printf "%s\t%s\n" "$src" "$html" >>"$TARGETS_FILE"
done

cat <<EOF
Exported online-doc HTML:

Output directory:
  $OUT_DIR

Target map:
  $TARGETS_FILE

HTML files:
$(find "$OUT_DIR" -maxdepth 1 -type f -name '*.html' -print | sort | sed 's/^/  /')
EOF
