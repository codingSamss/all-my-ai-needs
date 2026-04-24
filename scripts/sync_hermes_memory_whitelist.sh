#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
  cat <<'USAGE'
用法:
  ./scripts/sync_hermes_memory_whitelist.sh check [--format text|json]
  ./scripts/sync_hermes_memory_whitelist.sh apply --plan-id <plan_id> --approve-token <token>

说明:
  - 仅支持 local->repo 的 Hermes memory 白名单同步。
  - check 负责生成 plan_id + approve_token。
  - apply 必须使用 check 返回的 plan_id + approve_token。
USAGE
}

command="check"
format="text"
plan_id=""
approve_token=""

if [ $# -gt 0 ]; then
  case "$1" in
    check|apply)
      command="$1"
      shift
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
  esac
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --format)
      shift
      [ $# -gt 0 ] || { echo "[错误] --format 缺少参数"; exit 1; }
      format="$1"
      ;;
    --plan-id)
      shift
      [ $# -gt 0 ] || { echo "[错误] --plan-id 缺少参数"; exit 1; }
      plan_id="$1"
      ;;
    --approve-token)
      shift
      [ $# -gt 0 ] || { echo "[错误] --approve-token 缺少参数"; exit 1; }
      approve_token="$1"
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      echo "[错误] 未知参数: $1"
      usage
      exit 1
      ;;
  esac
  shift

done

case "$command" in
  check)
    "$SCRIPT_DIR/syncctl.sh" check \
      --direction local-to-repo \
      --platform hermes \
      --scope memory \
      --format "$format"
    ;;
  apply)
    [ -n "$plan_id" ] || { echo "[错误] apply 需要 --plan-id"; exit 1; }
    [ -n "$approve_token" ] || { echo "[错误] apply 需要 --approve-token"; exit 1; }
    "$SCRIPT_DIR/syncctl.sh" apply \
      --plan-id "$plan_id" \
      --approve-token "$approve_token"
    ;;
  *)
    echo "[错误] 未知命令: $command"
    usage
    exit 1
    ;;
esac
