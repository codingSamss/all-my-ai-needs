#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/skills/midea-recall-diagnose-playwright"

echo "[midea-recall-diagnose-playwright] 检查 Python3..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "[midea-recall-diagnose-playwright] 未检测到 Python3，请手动安装后重试"
  NEED_MANUAL=1
fi

echo "[midea-recall-diagnose-playwright] 检查 Claude CLI..."
if ! command -v claude >/dev/null 2>&1; then
  echo "[midea-recall-diagnose-playwright] 未检测到 claude 命令，请先安装 Claude Code"
  NEED_MANUAL=1
else
  echo "[midea-recall-diagnose-playwright] 检查 playwright-ext MCP..."
  if claude mcp list 2>/dev/null | rg -q "playwright-ext"; then
    echo "[midea-recall-diagnose-playwright] playwright-ext MCP 已配置"
  else
    echo "[midea-recall-diagnose-playwright] 未检测到 playwright-ext MCP，请先在 Claude 侧完成 MCP 配置"
    NEED_MANUAL=1
  fi
fi

echo "[midea-recall-diagnose-playwright] 同步 scripts -> $TARGET_DIR/scripts/"
mkdir -p "$TARGET_DIR/scripts"
for f in "$SCRIPT_DIR"/scripts/*.py; do
  [ -f "$f" ] || continue
  install -m 755 "$f" "$TARGET_DIR/scripts/$(basename "$f")"
  echo "  - $(basename "$f")"
done

echo "[midea-recall-diagnose-playwright] 同步 references -> $TARGET_DIR/references/"
mkdir -p "$TARGET_DIR/references"
for f in "$SCRIPT_DIR"/references/*; do
  [ -f "$f" ] || continue
  install -m 644 "$f" "$TARGET_DIR/references/$(basename "$f")"
  echo "  - $(basename "$f")"
done

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
