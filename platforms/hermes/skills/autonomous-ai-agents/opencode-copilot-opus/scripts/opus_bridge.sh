#!/usr/bin/env bash
set -euo pipefail

OC_BIN="${OPENCODE_BIN:-opencode}"
MODEL="${OPENCODE_MODEL:-github-copilot/claude-opus-4.6}"
SAFE_MODE="${OPENCODE_SAFE_MODE:-1}"

if [[ "$SAFE_MODE" == "1" ]]; then
  export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp}"
  export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/tmp}"
fi

usage() {
  cat <<'USAGE'
Usage:
  opus_bridge.sh auth
  opus_bridge.sh models
  opus_bridge.sh new <prompt>
  opus_bridge.sh continue <prompt>
  opus_bridge.sh list-sessions
  opus_bridge.sh latest-session
  opus_bridge.sh run-session <session_id> <prompt>

Env:
  OPENCODE_BIN        override opencode binary (default: opencode)
  OPENCODE_MODEL      override model (default: github-copilot/claude-opus-4.6)
  OPENCODE_SAFE_MODE  1=force XDG_CACHE_HOME/XDG_CONFIG_HOME to /tmp (default: 1)
USAGE
}

latest_session_id() {
  "$OC_BIN" session list | awk 'NR>2 && $1 ~ /^ses_/ {print $1; exit}'
}

cmd="${1:-}"
shift || true

case "$cmd" in
  auth)
    "$OC_BIN" auth list
    ;;
  models)
    "$OC_BIN" models | grep -Ei 'github-copilot/claude-opus|github-copilot/claude-sonnet|github-copilot/gpt-5|github-copilot/gemini' || true
    ;;
  new)
    if [[ $# -lt 1 ]]; then
      echo "Missing prompt" >&2
      usage
      exit 1
    fi
    "$OC_BIN" run -m "$MODEL" "$*"
    ;;
  continue)
    if [[ $# -lt 1 ]]; then
      echo "Missing prompt" >&2
      usage
      exit 1
    fi
    "$OC_BIN" run -c -m "$MODEL" "$*"
    ;;
  list-sessions)
    "$OC_BIN" session list
    ;;
  latest-session)
    sid="$(latest_session_id)"
    if [[ -z "$sid" ]]; then
      echo "No session found" >&2
      exit 1
    fi
    echo "$sid"
    ;;
  run-session)
    if [[ $# -lt 2 ]]; then
      echo "Need: <session_id> <prompt>" >&2
      usage
      exit 1
    fi
    sid="$1"
    shift
    "$OC_BIN" run -s "$sid" -m "$MODEL" "$*"
    ;;
  *)
    usage
    exit 1
    ;;
esac
