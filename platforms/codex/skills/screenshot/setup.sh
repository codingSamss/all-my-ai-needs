#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHOT_SCRIPT="$SCRIPT_DIR/scripts/take_screenshot.py"
PERM_SWIFT="$SCRIPT_DIR/scripts/macos_permissions.swift"
PERM_HELPER="$SCRIPT_DIR/scripts/ensure_macos_permissions.sh"

echo "[screenshot] 检查 Python3..."
if command -v python3 >/dev/null 2>&1; then
  echo "[screenshot] Python3 已安装"
else
  if command -v brew >/dev/null 2>&1; then
    echo "[screenshot] 安装 Python3"
    brew install python3
  else
    echo "[screenshot] 未检测到 Homebrew，请手动安装 Python3"
    NEED_MANUAL=1
  fi
fi

if [ ! -f "$SHOT_SCRIPT" ]; then
  echo "[screenshot] 缺少脚本: $SHOT_SCRIPT"
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  if python3 "$SHOT_SCRIPT" --help >/dev/null 2>&1; then
    echo "[screenshot] 截图脚本可运行"
  else
    echo "[screenshot] 截图脚本运行失败，请检查: $SHOT_SCRIPT"
    exit 1
  fi
fi

if [ "$(uname)" = "Darwin" ]; then
  echo "[screenshot] 检查 macOS 依赖..."
  if ! command -v screencapture >/dev/null 2>&1; then
    echo "[screenshot] 未检测到 screencapture（macOS 系统命令）"
    NEED_MANUAL=1
  fi

  if ! command -v swift >/dev/null 2>&1; then
    echo "[screenshot] 未检测到 swift，请先安装 Xcode Command Line Tools"
    NEED_MANUAL=1
  fi

  if [ ! -x "$PERM_HELPER" ]; then
    chmod +x "$PERM_HELPER" 2>/dev/null || true
  fi

  if command -v swift >/dev/null 2>&1 && [ -f "$PERM_SWIFT" ]; then
    MODULE_CACHE="${TMPDIR:-/tmp}/codex-swift-module-cache"
    mkdir -p "$MODULE_CACHE"
    perm_json="$(swift -module-cache-path "$MODULE_CACHE" "$PERM_SWIFT" 2>/dev/null || true)"
    if [ -n "$perm_json" ] && python3 - <<'PY' "$perm_json"
import json, sys
try:
    data = json.loads(sys.argv[1])
    print("1" if data.get("screenCapture") else "0")
except Exception:
    print("0")
PY
    then
      perm_ok="$(python3 - <<'PY' "$perm_json"
import json, sys
try:
    data = json.loads(sys.argv[1])
    print("1" if data.get("screenCapture") else "0")
except Exception:
    print("0")
PY
)"
      if [ "$perm_ok" = "1" ]; then
        echo "[screenshot] 屏幕录制权限已授权"
      else
        echo "[screenshot] 屏幕录制权限未授权，请手动执行: $PERM_HELPER"
        NEED_MANUAL=1
      fi
    else
      echo "[screenshot] 无法读取屏幕录制权限状态，请手动执行: $PERM_HELPER"
      NEED_MANUAL=1
    fi
  fi
elif [ "$(uname)" = "Linux" ]; then
  echo "[screenshot] 检查 Linux 截图命令..."
  if command -v scrot >/dev/null 2>&1 || command -v gnome-screenshot >/dev/null 2>&1 || command -v import >/dev/null 2>&1; then
    echo "[screenshot] Linux 截图命令已就绪"
  else
    echo "[screenshot] 未检测到 scrot/gnome-screenshot/import，请手动安装其中任意一个"
    NEED_MANUAL=1
  fi
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
