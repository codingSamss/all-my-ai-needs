#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
MCP_READY=0

echo "[playwright] 检查 playwright-ext MCP..."
if command -v claude >/dev/null 2>&1; then
  if claude mcp list 2>/dev/null | grep -q "playwright-ext"; then
    echo "[playwright] playwright-ext MCP 已就绪"
    MCP_READY=1
  else
    echo "[playwright] 未检测到 playwright-ext MCP，请先配置："
    echo "  ./setup.sh core"
    echo "  claude mcp list | rg \"playwright-ext\""
    NEED_MANUAL=1
  fi
else
  echo "[playwright] 未检测到 claude 命令，请先安装/配置 Claude Code CLI"
  NEED_MANUAL=1
fi

echo "[playwright] 检查 npx..."
if command -v npx >/dev/null 2>&1; then
  echo "[playwright] npx 已安装"
else
  if command -v brew >/dev/null 2>&1; then
    echo "[playwright] 安装 Node.js（提供 npx）"
    brew install node
  else
    echo "[playwright] 未检测到 Homebrew，请手动安装 Node.js/npm"
    NEED_MANUAL=1
  fi
fi

if [ "$MCP_READY" -eq 1 ]; then
  echo "[playwright] 统一使用 playwright-ext MCP"
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
