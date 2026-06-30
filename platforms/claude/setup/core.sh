#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[core] 配置公共组件..."

# hooks（使用复制，避免软链接失效）
echo "[core] 复制 hooks/notify.sh -> ~/.claude/hooks/notify.sh"
mkdir -p "$HOME/.claude/hooks"
install -m 755 "$PLUGIN_DIR/hooks/notify.sh" "$HOME/.claude/hooks/notify.sh"

# scripts（使用复制，避免软链接失效）
echo "[core] 同步 scripts -> ~/.claude/scripts/"
mkdir -p "$HOME/.claude/scripts"
for script in "$PLUGIN_DIR"/scripts/*; do
  [ -f "$script" ] || continue
  name="$(basename "$script")"
  install -m 755 "$script" "$HOME/.claude/scripts/$name"
  echo "  - $name"
done

# agents（使用复制，避免软链接失效）
echo "[core] 复制 agents -> ~/.claude/agents/"
mkdir -p "$HOME/.claude/agents"
for agent in "$PLUGIN_DIR"/agents/*.md; do
  [ -f "$agent" ] || continue
  name="$(basename "$agent")"
  install -m 644 "$agent" "$HOME/.claude/agents/$name"
  echo "  - $name"
done

# CLAUDE.md（全局指令同步到 ~/.claude/CLAUDE.md，覆盖前需用户确认）
if [ -f "$PLUGIN_DIR/CLAUDE.md" ]; then
  TARGET_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
  if [ -f "$TARGET_CLAUDE_MD" ] && ! diff -q "$PLUGIN_DIR/CLAUDE.md" "$TARGET_CLAUDE_MD" >/dev/null 2>&1; then
    echo "[core] 检测到 ~/.claude/CLAUDE.md 与仓库版本存在差异："
    diff --color=auto "$TARGET_CLAUDE_MD" "$PLUGIN_DIR/CLAUDE.md" || true
    if [ ! -t 0 ]; then
      echo "[core] 非交互环境，默认跳过覆盖 ~/.claude/CLAUDE.md（保留本地版本）"
      answer="n"
    else
      printf "[core] 是否用仓库版本覆盖 ~/.claude/CLAUDE.md？[y/N] "
      read -r answer || answer=""
    fi
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
      install -m 644 "$PLUGIN_DIR/CLAUDE.md" "$TARGET_CLAUDE_MD"
      echo "[core] CLAUDE.md 已覆盖"
    else
      echo "[core] 跳过 CLAUDE.md（保留本地版本）"
    fi
  elif [ ! -f "$TARGET_CLAUDE_MD" ]; then
    echo "[core] 复制 CLAUDE.md -> ~/.claude/CLAUDE.md（首次安装）"
    install -m 644 "$PLUGIN_DIR/CLAUDE.md" "$TARGET_CLAUDE_MD"
  else
    echo "[core] CLAUDE.md 无变化，跳过"
  fi
fi

# .mcp.json（自动合并缺失的 MCP server，不覆盖已有配置）
MCP_TEMPLATE="$PLUGIN_DIR/.mcp.json"
LOCAL_MCP="$HOME/.claude.json"
if [ -f "$MCP_TEMPLATE" ] && [ -f "$LOCAL_MCP" ]; then
  echo "[core] 同步 MCP server 配置..."
  MCP_ERR_FILE="$(mktemp /tmp/claude-core-mcp-merge.XXXXXX.err)"
  MCP_RESULT=$(python3 - "$MCP_TEMPLATE" "$LOCAL_MCP" 2>"$MCP_ERR_FILE" <<'PYEOF'
import json, sys, re

tpl_path, local_path = sys.argv[1], sys.argv[2]

with open(tpl_path, encoding="utf-8") as f:
    tpl_root = json.load(f)
with open(local_path, encoding="utf-8") as f:
    local_root = json.load(f)

tpl = tpl_root.get("mcpServers", {})
local = local_root.setdefault("mcpServers", {})

if not isinstance(tpl, dict) or not isinstance(local, dict):
    raise ValueError("mcpServers 字段必须是对象")

PLACEHOLDER_RE = re.compile(r"<[A-Z_]+>")
added, placeholder = [], []

for name, cfg in tpl.items():
    if name in local:
        continue
    local[name] = cfg
    added.append(name)
    raw = json.dumps(cfg)
    if PLACEHOLDER_RE.search(raw):
        placeholder.append(name)

if added:
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(local_root, f, indent=2, ensure_ascii=False)
        f.write("\n")

print(f"ADDED:{','.join(added)}")
print(f"PLACEHOLDER:{','.join(placeholder)}")
PYEOF
  ) || true

  if [ -s "$MCP_ERR_FILE" ]; then
    echo "[core] MCP 合并出错，请确认 JSON 格式："
    sed 's/^/[core]   /' "$MCP_ERR_FILE"
  elif [ -n "$MCP_RESULT" ]; then
    MCP_ADDED=$(echo "$MCP_RESULT" | grep '^ADDED:' | cut -d: -f2)
    MCP_PH=$(echo "$MCP_RESULT" | grep '^PLACEHOLDER:' | cut -d: -f2)
    if [ -n "$MCP_ADDED" ]; then
      echo "[core] 已自动写入以下 MCP server："
      echo "$MCP_ADDED" | tr ',' '\n' | while read -r name; do
        [ -n "$name" ] && echo "  + $name"
      done
      if [ -n "$MCP_PH" ]; then
        echo "[core] 以下 server 含占位符密钥，需替换为真实值："
        echo "$MCP_PH" | tr ',' '\n' | while read -r name; do
          [ -n "$name" ] && echo "  ! $name"
        done
      fi
    else
      echo "[core] MCP server 配置完整，无缺失"
    fi
  else
    echo "[core] MCP server 配置完整，无缺失"
  fi
  rm -f "$MCP_ERR_FILE"
elif [ -f "$MCP_TEMPLATE" ] && [ ! -f "$LOCAL_MCP" ]; then
  echo "[core] 未找到 ~/.claude.json，初始化 MCP 配置..."
  python3 -c "
import json, sys, shutil
tpl_path = sys.argv[1]
local_path = sys.argv[2]
with open(tpl_path, encoding='utf-8') as f:
    tpl = json.load(f)
with open(local_path, 'w', encoding='utf-8') as f:
    json.dump(tpl, f, indent=2, ensure_ascii=False)
    f.write('\n')
" "$MCP_TEMPLATE" "$LOCAL_MCP"
  echo "[core] 已从模板初始化 ~/.claude.json（含占位符密钥需替换）"
fi

# skills（同步运行所需最小文件到 ~/.claude/skills/；runtime.yaml 留在 repo）
echo "[core] 同步 skills -> ~/.claude/skills/"
sync_skill_root() {
  local source_root="$1"
  local skill_dir=""
  local skill_name=""
  local target_dir=""
  local sub=""
  local sub_name=""

  [ -d "$source_root" ] || return 0

  for skill_dir in "$source_root"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    target_dir="$HOME/.claude/skills/$skill_name"
    # 清理后重建，确保已删除的文件不会残留
    rm -rf "$target_dir"
    mkdir -p "$target_dir"
    # 同步 SKILL.md
    if [ -f "$skill_dir/SKILL.md" ]; then
      install -m 644 "$skill_dir/SKILL.md" "$target_dir/SKILL.md"
    fi
    # 同步子目录（如 scripts/、references/、assets/）；Claude 运行目录不带 agents/ 与 runtime.yaml
    for sub in "$skill_dir"*/; do
      [ -d "$sub" ] || continue
      sub_name="$(basename "${sub%/}")"
      if [ "$sub_name" = "agents" ]; then
        continue
      fi
      # bird-twitter 的 vendor 为 repo-only 备份资产，不下发到本地运行目录
      if [ "$skill_name" = "bird-twitter" ] && [ "$sub_name" = "vendor" ]; then
        continue
      fi
      cp -r "${sub%/}" "$target_dir/"
    done
    echo "  - $skill_name"
  done
}

sync_skill_root "$PLUGIN_DIR/skills"

echo "[core] 完成"
