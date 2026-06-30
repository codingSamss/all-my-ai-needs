#!/bin/bash
set -euo pipefail

CLAUDE_JSON="$HOME/.claude.json"

echo "[cc-codex-review] 检查 Codex MCP 配置..."
if [ -f "$CLAUDE_JSON" ] && python3 -c "
import json, sys
with open('$CLAUDE_JSON') as f:
    cfg = json.load(f)
sys.exit(0 if 'codex' in cfg.get('mcpServers', {}) else 1)
" 2>/dev/null; then
  echo "[cc-codex-review] codex MCP 已配置"
else
  echo "[cc-codex-review] 未检测到 codex MCP，请执行:"
  echo "  claude mcp add codex -s user --transport stdio -- uvx --from git+https://github.com/codingSamss/codexmcp.git codexmcp"
  exit 2
fi
