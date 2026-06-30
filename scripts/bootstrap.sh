#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_PROXY="http://127.0.0.1:7897"

# 默认走本地代理；若用户已显式设置则尊重用户设置
: "${HTTP_PROXY:=$DEFAULT_PROXY}"
: "${HTTPS_PROXY:=$DEFAULT_PROXY}"
export HTTP_PROXY HTTPS_PROXY
export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY"

usage() {
  cat <<'USAGE'
用法:
  ./scripts/bootstrap.sh all      # Claude + Codex
  ./scripts/bootstrap.sh claude   # 仅 Claude
  ./scripts/bootstrap.sh codex    # 仅 Codex

退出码:
  0: 全部自动完成
  1: 存在失败
  2: 存在需手动完成项（无失败）
USAGE
}

run_claude_setup() {
  local code=0
  if "$REPO_ROOT/setup.sh" all; then
    code=0
  else
    code=$?
  fi

  if [ "$code" -eq 0 ]; then
    return 0
  fi

  if [ "$code" -eq 2 ]; then
    return 2
  fi
  return 1
}

run_codex_sync() {
  "$REPO_ROOT/scripts/sync_to_codex.sh"
}

run_codex_setup() {
  local skills_root="$REPO_ROOT/platforms/codex/skills"
  local manual_required=0
  local failed=0
  local skill_dir

  if [ ! -d "$skills_root" ]; then
    echo "[codex-setup] 未找到 skills 目录: $skills_root"
    return 1
  fi

  echo "[codex-setup] 执行 Codex skills 依赖检查..."
  while IFS= read -r skill_dir; do
    local skill_name
    local script
    local code=0

    skill_name="$(basename "$skill_dir")"
    script="$skill_dir/setup.sh"

    if [ ! -f "$script" ]; then
      echo "  - [跳过] $skill_name 未提供 setup.sh"
      continue
    fi

    echo "  - [开始] $skill_name"
    if bash "$script"; then
      code=0
    else
      code=$?
    fi

    if [ "$code" -eq 0 ]; then
      echo "  - [完成] ${skill_name}（自动完成）"
    elif [ "$code" -eq 2 ]; then
      manual_required=1
      echo "  - [完成] ${skill_name}（需手动）"
    else
      failed=1
      echo "  - [失败] ${skill_name}（exit=${code}）"
    fi
  done < <(find "$skills_root" -mindepth 1 -maxdepth 1 -type d | sort)

  if [ "$failed" -eq 1 ]; then
    return 1
  fi

  if [ "$manual_required" -eq 1 ]; then
    return 2
  fi

  return 0
}

target="${1:-all}"
status=0

echo "=== 新机初始化引导 ==="

case "$target" in
  all)
    echo "[1/3] 配置 Claude Code 侧..."
    if run_claude_setup; then
      echo "[1/3] Claude 侧自动完成"
    else
      code=$?
      if [ "$code" -eq 2 ]; then
        echo "[1/3] Claude 侧存在需手动完成项"
        status=2
      else
        echo "[1/3] Claude 侧执行失败"
        exit 1
      fi
    fi

    echo "[2/3] 同步 Codex 配置（skills + root 受管配置，默认不覆盖本机 config.toml）..."
    run_codex_sync
    echo "[2/3] Codex 配置同步完成"

    echo "[3/3] 执行 Codex skills 初始化..."
    if run_codex_setup; then
      echo "[3/3] Codex skills 自动完成"
    else
      code=$?
      if [ "$code" -eq 2 ]; then
        echo "[3/3] Codex skills 存在需手动完成项"
        status=2
      else
        echo "[3/3] Codex skills 执行失败"
        exit 1
      fi
    fi
    ;;
  claude)
    echo "[1/1] 配置 Claude Code 侧..."
    if run_claude_setup; then
      status=0
    else
      code=$?
      if [ "$code" -eq 2 ]; then
        status=2
      else
        exit 1
      fi
    fi
    ;;
  codex)
    echo "[1/2] 同步 Codex 配置（skills + root 受管配置，默认不覆盖本机 config.toml）..."
    run_codex_sync
    echo "[1/2] Codex 配置同步完成"
    echo "[2/2] 执行 Codex skills 初始化..."
    if run_codex_setup; then
      status=0
    else
      code=$?
      if [ "$code" -eq 2 ]; then
        status=2
      else
        exit 1
      fi
    fi
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "[错误] 未知目标: $target"
    usage
    exit 1
    ;;
esac

echo ""
if [ "$status" -eq 2 ]; then
  echo "初始化已完成，但存在需手动补齐项。"
  echo "建议按 setup 汇总清单逐项补齐后再执行一次。"
  exit 2
fi

echo "初始化完成。建议重启 Claude Code 与 Codex 客户端。"
