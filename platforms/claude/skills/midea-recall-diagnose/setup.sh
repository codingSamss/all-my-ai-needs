#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/skills/midea-recall-diagnose"
SKILL_NAME="midea-recall-diagnose"

echo "[$SKILL_NAME] 检查 Python3..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "[$SKILL_NAME] 未检测到 Python3，请手动安装后重试"
  NEED_MANUAL=1
fi

echo "[$SKILL_NAME] 检查 Python 依赖..."
if command -v python3 >/dev/null 2>&1; then
  if python3 - <<'PY' >/dev/null 2>&1
import browser_cookie3
import requests
import yaml
PY
  then
    echo "[$SKILL_NAME] Python 依赖已就绪"
  else
    echo "[$SKILL_NAME] 缺少 Python 依赖，请安装: browser_cookie3 requests PyYAML"
    NEED_MANUAL=1
  fi
fi

echo "[$SKILL_NAME] 检查 Claude CLI..."
if ! command -v claude >/dev/null 2>&1; then
  echo "[$SKILL_NAME] 未检测到 claude 命令，请先安装 Claude Code"
  NEED_MANUAL=1
fi

echo "[$SKILL_NAME] 同步 scripts -> $TARGET_DIR/scripts/"
mkdir -p "$TARGET_DIR/scripts"
for f in "$SCRIPT_DIR"/scripts/*.py; do
  [ -f "$f" ] || continue
  install -m 755 "$f" "$TARGET_DIR/scripts/$(basename "$f")"
  echo "  - $(basename "$f")"
done

echo "[$SKILL_NAME] 同步 references -> $TARGET_DIR/references/"
mkdir -p "$TARGET_DIR/references"
for f in "$SCRIPT_DIR"/references/*; do
  [ -f "$f" ] || continue
  install -m 644 "$f" "$TARGET_DIR/references/$(basename "$f")"
  echo "  - $(basename "$f")"
done

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
