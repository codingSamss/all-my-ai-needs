#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_ROOT="$SCRIPT_DIR/platforms/claude"
SKILLS_ROOT="$CLAUDE_ROOT/skills"
SHARED_SKILLS_ROOT="$SCRIPT_DIR/shared/skills"
CORE_SETUP="$CLAUDE_ROOT/setup/core.sh"
DEFAULT_PROXY="http://127.0.0.1:7897"

# 默认走本地代理；若用户已显式设置则尊重用户设置
: "${HTTP_PROXY:=$DEFAULT_PROXY}"
: "${HTTPS_PROXY:=$DEFAULT_PROXY}"
export HTTP_PROXY HTTPS_PROXY
export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY"

SUCCEEDED=()
MANUAL_REQUIRED=()
FAILED=()
SKIPPED=()

print_usage() {
  cat <<'USAGE'
用法:
  ./setup.sh                 # 执行 core + 全部 skill 配置
  ./setup.sh all             # 同上
  ./setup.sh list            # 列出可配置 skill
  ./setup.sh core            # 仅执行公共配置
  ./setup.sh <skill...>      # 仅执行指定 skill，例如 ./setup.sh reddit peekaboo

说明:
  日常共享 skill 同步默认由 AI 手工 diff 后做最小落盘。
  本脚本主要用于 Claude 侧 bootstrap / 灾备 fallback。

退出码:
  0: 全部自动完成
  1: 存在失败项
  2: 存在需手动完成项（无失败）
USAGE
}

list_skills() {
  {
    [ -d "$SHARED_SKILLS_ROOT" ] && find "$SHARED_SKILLS_ROOT" -mindepth 1 -maxdepth 1 -type d -exec basename {} \;
    [ -d "$SKILLS_ROOT" ] && find "$SKILLS_ROOT" -mindepth 1 -maxdepth 1 -type d -exec basename {} \;
  } | sort -u
}

resolve_skill_dir() {
  local skill="$1"

  if [ -d "$SKILLS_ROOT/$skill" ]; then
    echo "$SKILLS_ROOT/$skill"
    return 0
  fi

  if [ -d "$SHARED_SKILLS_ROOT/$skill" ]; then
    echo "$SHARED_SKILLS_ROOT/$skill"
    return 0
  fi

  return 1
}

record_result() {
  local type="$1"
  local item="$2"

  case "$type" in
    success)
      SUCCEEDED+=("$item")
      ;;
    manual)
      MANUAL_REQUIRED+=("$item")
      ;;
    fail)
      FAILED+=("$item")
      ;;
    skip)
      SKIPPED+=("$item")
      ;;
  esac
}

print_group() {
  local title="$1"
  shift
  local arr=("$@")

  echo "$title (${#arr[@]}):"
  local i
  for i in "${arr[@]}"; do
    echo "  - $i"
  done
}

print_summary() {
  echo ""
  echo "=== 配置汇总 ==="

  if [ ${#SUCCEEDED[@]} -gt 0 ]; then
    print_group "自动完成" "${SUCCEEDED[@]}"
  fi

  if [ ${#MANUAL_REQUIRED[@]} -gt 0 ]; then
    print_group "需手动完成" "${MANUAL_REQUIRED[@]}"
  fi

  if [ ${#FAILED[@]} -gt 0 ]; then
    print_group "执行失败" "${FAILED[@]}"
  fi

  if [ ${#SKIPPED[@]} -gt 0 ]; then
    print_group "已跳过" "${SKIPPED[@]}"
  fi
}

run_script() {
  local name="$1"
  local script="$2"

  if [ ! -f "$script" ]; then
    echo "[跳过] $name 未提供 setup 脚本: $script"
    record_result skip "$name"
    return 0
  fi

  echo ""
  echo "=== 开始: $name ==="

  local code=0
  if bash "$script"; then
    code=0
  else
    code=$?
  fi

  if [ "$code" -eq 0 ]; then
    record_result success "$name"
    echo "=== 完成: ${name}（自动完成）==="
  elif [ "$code" -eq 2 ]; then
    record_result manual "$name"
    echo "=== 完成: ${name}（需手动）==="
  else
    record_result fail "$name (exit=$code)"
    echo "=== 失败: ${name}（exit=${code}）==="
  fi

  return 0
}

run_core() {
  run_script "core" "$CORE_SETUP"
}

run_skill() {
  local skill="$1"
  local skill_dir=""
  local script=""

  if ! skill_dir="$(resolve_skill_dir "$skill")"; then
    echo "[错误] 未找到 skill: $skill"
    record_result fail "$skill (未找到)"
    return 0
  fi

  script="$skill_dir/setup.sh"
  if [ ! -f "$script" ]; then
    echo "[信息] $skill 无额外 setup 脚本；core 已负责同步必要文件"
    record_result success "$skill (core-only)"
    return 0
  fi

  run_script "$skill" "$script"
}

validate_skills_or_exit() {
  local missing=0
  local skill
  for skill in "$@"; do
    if ! resolve_skill_dir "$skill" >/dev/null; then
      echo "[错误] 未找到 skill: $skill"
      missing=1
    fi
  done

  if [ "$missing" -eq 1 ]; then
    echo ""
    echo "存在无效 skill 参数，请先修正后重试。"
    exit 1
  fi
}

finalize_and_exit() {
  print_summary

  if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "存在失败项，请先修复失败后再重试。"
    exit 1
  fi

  if [ ${#MANUAL_REQUIRED[@]} -gt 0 ]; then
    echo ""
    echo "存在需手动完成项，请按上面的清单补齐。"
    exit 2
  fi

  echo ""
  echo "全部自动配置完成。请重启 Claude Code 以加载最新配置。"
  exit 0
}

main() {
  local args=("$@")

  echo "=== Claude 平台 Setup（可审计模式）==="
  echo "Claude 源目录: $CLAUDE_ROOT"

  if [ ! -d "$CLAUDE_ROOT" ]; then
    echo "[错误] Claude 平台目录不存在: $CLAUDE_ROOT"
    exit 1
  fi

  if [ ${#args[@]} -gt 0 ]; then
    case "${args[0]}" in
      list)
        echo "可配置 skills:"
        list_skills
        exit 0
        ;;
      -h|--help|help)
        print_usage
        exit 0
        ;;
    esac
  fi

  if [ ${#args[@]} -eq 0 ] || [ "${args[0]}" = "all" ]; then
    run_core
    while IFS= read -r skill; do
      run_skill "$skill"
    done < <(list_skills)
    finalize_and_exit
  fi

  case "${args[0]}" in
    list)
      echo "可配置 skills:"
      list_skills
      exit 0
      ;;
    core)
      run_core
      finalize_and_exit
      ;;
    -h|--help|help)
      print_usage
      exit 0
      ;;
    *)
      validate_skills_or_exit "${args[@]}"
      run_core
      local skill
      for skill in "${args[@]}"; do
        run_skill "$skill"
      done
      finalize_and_exit
      ;;
  esac
}

main "$@"
