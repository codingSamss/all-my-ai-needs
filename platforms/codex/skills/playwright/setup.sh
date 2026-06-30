#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
MCP_READY=0

echo "[playwright] 检查 playwright-ext MCP..."
if command -v codex >/dev/null 2>&1; then
  MCP_INFO="$(codex mcp get playwright-ext 2>/dev/null || true)"
  if printf '%s\n' "$MCP_INFO" | grep -q "(disabled)"; then
    echo "[playwright] playwright-ext MCP 当前为 disabled，请先手动启用后再使用本 skill"
    NEED_MANUAL=1
  elif [ -n "$MCP_INFO" ]; then
    echo "[playwright] playwright-ext MCP 已就绪"
    MCP_READY=1
  else
    echo "[playwright] 未检测到 playwright-ext MCP，请先配置："
    echo "  codex mcp add playwright-ext --env PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> -- npx @playwright/mcp@latest --extension"
    NEED_MANUAL=1
  fi
else
  echo "[playwright] 未检测到 codex 命令，请先安装/配置 codex CLI"
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
