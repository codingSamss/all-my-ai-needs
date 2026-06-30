#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/scripts/session_diary.py"

echo "[orbit-session-diary] 检查 Python3..."
if ! command -v python3 >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "[orbit-session-diary] 安装 Python3"
    brew install python3
  else
    echo "[orbit-session-diary] 未检测到 Python3，且无 Homebrew，请手动安装 Python3"
    NEED_MANUAL=1
  fi
fi

if [ ! -f "$SCRIPT_PATH" ]; then
  echo "[orbit-session-diary] 缺少脚本: $SCRIPT_PATH"
  exit 1
fi

chmod +x "$SCRIPT_PATH"

if [ ! -d "$HOME/.codex/sessions" ] && [ ! -d "$HOME/.claude/projects" ]; then
  echo "[orbit-session-diary] 提示：尚未检测到会话目录，首次使用前可先产生会话日志"
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
