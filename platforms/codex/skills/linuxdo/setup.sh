#!/bin/bash
set -euo pipefail

NEED_MANUAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SCRIPT="$SCRIPT_DIR/scripts/linuxdo.py"
CHROME_COOKIES="$HOME/Library/Application Support/Google/Chrome/Default/Cookies"
PROXY_HTTPS="${HTTPS_PROXY:-${HTTP_PROXY:-http://127.0.0.1:7897}}"

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

if [ ! -f "$SKILL_SCRIPT" ]; then
  echo "[linuxdo] 缺少脚本: $SKILL_SCRIPT"
  exit 1
fi

chmod +x "$SKILL_SCRIPT"

# 检查 Chrome Cookie DB（用于受限内容）
echo "[linuxdo] 检查 Chrome Cookies 数据库..."
if [ -f "$CHROME_COOKIES" ]; then
  echo "[linuxdo] Chrome Cookies 数据库存在"
else
  echo "[linuxdo] 未找到 Chrome Cookies 数据库: $CHROME_COOKIES"
  echo "[linuxdo] 请确认已安装 Chrome 并登录过 linux.do"
  NEED_MANUAL=1
fi

# 检查 API 可达性
echo "[linuxdo] 检查 linux.do API 可达性..."
if command -v python3 >/dev/null 2>&1; then
  REACH_OK=0

  if python3 "$SKILL_SCRIPT" --cookie "test=1" latest --limit 1 >/dev/null 2>&1; then
    REACH_OK=1
  elif [ -n "$PROXY_HTTPS" ]; then
    if HTTPS_PROXY="$PROXY_HTTPS" python3 "$SKILL_SCRIPT" --cookie "test=1" latest --limit 1 >/dev/null 2>&1; then
      REACH_OK=1
    fi
  fi

  if [ "$REACH_OK" -eq 1 ]; then
    echo "[linuxdo] API 可达"
  else
    echo "[linuxdo] 无法访问 linux.do，请检查网络连通性或代理配置"
    echo "  HTTPS_PROXY=http://127.0.0.1:7897 python3 $SKILL_SCRIPT latest --limit 3"
    NEED_MANUAL=1
  fi
fi

# 非阻塞认证检查：若失败仍允许公共内容使用
echo "[linuxdo] 检查 Chrome Cookie 认证..."
if command -v python3 >/dev/null 2>&1; then
  AUTH_RESULT=$(HTTPS_PROXY="$PROXY_HTTPS" python3 "$SKILL_SCRIPT" whoami 2>&1) || true
  if echo "$AUTH_RESULT" | grep -q "用户名:"; then
    echo "[linuxdo] Chrome Cookie 认证成功"
    echo "$AUTH_RESULT" | head -2
  else
    echo "[linuxdo] Chrome Cookie 认证未通过（仍可访问公开内容）"
    echo "[linuxdo] 如需访问受限内容，请确保 Chrome 已登录 linux.do 并授权 Keychain 访问"
  fi
fi

if [ "$NEED_MANUAL" -eq 1 ]; then
  exit 2
fi
