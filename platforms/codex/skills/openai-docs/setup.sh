#!/bin/bash
set -euo pipefail

NEED_MANUAL=0

if ! command -v codex >/dev/null 2>&1; then
  echo "[openai-docs] 未检测到 codex 命令，请先安装 Codex CLI"
  NEED_MANUAL=1
else
  echo "[openai-docs] 检查 openaiDeveloperDocs MCP..."
  if codex mcp list 2>/dev/null | grep -qE '^openaiDeveloperDocs[[:space:]]'; then
    echo "[openai-docs] openaiDeveloperDocs MCP 已配置"
  else
    echo "[openai-docs] openaiDeveloperDocs MCP 未配置"
    echo "[openai-docs] 请手动执行："
    echo "  codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp"
    echo "[openai-docs] 配置后建议重启 Codex 客户端"
    NEED_MANUAL=1
  fi
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
