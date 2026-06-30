#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/skills/linuxdo"

echo "[linuxdo] 检查 Python3..."
if ! command -v python3 >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "[linuxdo] 安装 Python3"
    brew install python3
  else
    echo "[linuxdo] 未检测到 Python3，且无 Homebrew，请手动安装 Python3"
    NEED_MANUAL=1
  fi
fi

# 同步 scripts/ 到 ~/.claude/skills/linuxdo/scripts/（core.sh 只同步 SKILL.md）
echo "[linuxdo] 同步 scripts -> $TARGET_DIR/scripts/"
mkdir -p "$TARGET_DIR/scripts"
if [ -f "$SCRIPT_DIR/scripts/linuxdo.py" ]; then
  install -m 755 "$SCRIPT_DIR/scripts/linuxdo.py" "$TARGET_DIR/scripts/linuxdo.py"
  echo "[linuxdo] linuxdo.py 已同步"
else
  echo "[linuxdo] 缺少脚本: $SCRIPT_DIR/scripts/linuxdo.py"
  exit 1
fi

# 检查 Chrome Cookies 数据库
CHROME_COOKIES="$HOME/Library/Application Support/Google/Chrome/Default/Cookies"
echo "[linuxdo] 检查 Chrome Cookies 数据库..."
if [ -f "$CHROME_COOKIES" ]; then
  echo "[linuxdo] Chrome Cookies 数据库存在"
else
  echo "[linuxdo] 未找到 Chrome Cookies 数据库: $CHROME_COOKIES"
  echo "[linuxdo] 请确认已安装 Chrome 并登录过 linux.do"
  NEED_MANUAL=1
fi

# 检查 linux.do 可达性
PROXY_HTTPS="${HTTPS_PROXY:-${HTTP_PROXY:-}}"
echo "[linuxdo] 检查 linux.do API 可达性..."
if command -v python3 >/dev/null 2>&1; then
  REACH_OK=0
  if python3 "$TARGET_DIR/scripts/linuxdo.py" --cookie "test=1" latest --limit 1 >/dev/null 2>&1; then
    REACH_OK=1
  elif [ -n "$PROXY_HTTPS" ]; then
    if HTTPS_PROXY="$PROXY_HTTPS" python3 "$TARGET_DIR/scripts/linuxdo.py" --cookie "test=1" latest --limit 1 >/dev/null 2>&1; then
      REACH_OK=1
    fi
  fi

  if [ "$REACH_OK" -eq 1 ]; then
    echo "[linuxdo] API 可达"
  else
    echo "[linuxdo] 无法访问 linux.do，请检查网络连通性或代理配置"
    echo "  HTTPS_PROXY=http://127.0.0.1:7897 python3 $TARGET_DIR/scripts/linuxdo.py latest --limit 3"
    NEED_MANUAL=1
  fi
fi

# Chrome Cookie 认证测试（非阻塞）
echo "[linuxdo] 检查 Chrome Cookie 认证..."
if command -v python3 >/dev/null 2>&1; then
  AUTH_RESULT=$(python3 "$TARGET_DIR/scripts/linuxdo.py" whoami 2>&1) || true
  if echo "$AUTH_RESULT" | grep -q "用户名:"; then
    echo "[linuxdo] Chrome Cookie 认证成功"
    echo "$AUTH_RESULT" | head -2
  else
    echo "[linuxdo] Chrome Cookie 认证未通过（仍可访问公开内容）"
    echo "[linuxdo] 如需访问受限内容，请确保 Chrome 已登录 linux.do 并授权 Keychain 访问"
    # 不设 NEED_MANUAL——公开内容可用即可
  fi
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
