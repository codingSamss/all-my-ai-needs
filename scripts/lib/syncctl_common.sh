#!/bin/bash

set -euo pipefail

SYNCCTL_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SYNCCTL_PLAN_ROOT="${SYNCCTL_PLAN_ROOT:-/tmp/all-my-ai-needs-syncctl/plans}"
SYNCCTL_TASK_SEQ=0

syncctl_next_task_id() {
  SYNCCTL_TASK_SEQ=$((SYNCCTL_TASK_SEQ + 1))
  printf "task-%04d\n" "$SYNCCTL_TASK_SEQ"
}

syncctl_die() {
  echo "[syncctl][错误] $*" >&2
  exit 1
}

syncctl_now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

syncctl_generate_plan_id() {
  local ts
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  printf "plan-%s-%04d\n" "$ts" "$((RANDOM % 10000))"
}

syncctl_sanitize_field() {
  local s="$1"
  s="${s//$'\t'/ }"
  s="${s//$'\n'/ }"
  printf "%s" "$s"
}

syncctl_scope_includes() {
  local scope="$1"
  local needle="$2"
  [ "$scope" = "all" ] || [ "$scope" = "$needle" ]
}

syncctl_skill_selected() {
  local skill_name="$1"
  local skill_rel="$2"

  if [ "${#SYNCCTL_SKILL_FILTERS[@]}" -eq 0 ]; then
    return 0
  fi

  local f
  for f in "${SYNCCTL_SKILL_FILTERS[@]}"; do
    [ "$f" = "$skill_name" ] && return 0
    [ "$f" = "$skill_rel" ] && return 0
  done

  return 1
}

syncctl_add_task() {
  local tasks_file="$1"
  local task_id="$2"
  local platform="$3"
  local direction="$4"
  local scope="$5"
  local target="$6"
  local kind="$7"
  local src="$8"
  local dst="$9"
  local delete_policy="${10}"
  local excludes="${11}"
  local label="${12}"
  local reason="${13}"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(syncctl_sanitize_field "$task_id")" \
    "$(syncctl_sanitize_field "$platform")" \
    "$(syncctl_sanitize_field "$direction")" \
    "$(syncctl_sanitize_field "$scope")" \
    "$(syncctl_sanitize_field "$target")" \
    "$(syncctl_sanitize_field "$kind")" \
    "$(syncctl_sanitize_field "$src")" \
    "$(syncctl_sanitize_field "$dst")" \
    "$(syncctl_sanitize_field "$delete_policy")" \
    "$(syncctl_sanitize_field "$excludes")" \
    "$(syncctl_sanitize_field "$label")" \
    "$(syncctl_sanitize_field "$reason")" \
    >> "$tasks_file"
}

syncctl_add_op() {
  local ops_file="$1"
  local action="$2"
  local platform="$3"
  local scope="$4"
  local target="$5"
  local rel_path="$6"
  local src="$7"
  local dst="$8"
  local require_allow_delete="$9"
  local reason="${10}"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(syncctl_sanitize_field "$action")" \
    "$(syncctl_sanitize_field "$platform")" \
    "$(syncctl_sanitize_field "$scope")" \
    "$(syncctl_sanitize_field "$target")" \
    "$(syncctl_sanitize_field "$rel_path")" \
    "$(syncctl_sanitize_field "$src")" \
    "$(syncctl_sanitize_field "$dst")" \
    "$(syncctl_sanitize_field "$require_allow_delete")" \
    "$(syncctl_sanitize_field "$reason")" \
    >> "$ops_file"
}

syncctl_compute_token() {
  local direction="$1"
  local mode="$2"
  local tasks_file="$3"
  local ops_file="$4"

  {
    printf 'direction=%s\n' "$direction"
    printf 'mode=%s\n' "$mode"
    printf '%s\n' '--tasks--'
    cat "$tasks_file"
    printf '%s\n' '--ops--'
    cat "$ops_file"
  } | shasum -a 256 | awk '{print $1}'
}

syncctl_count_ops_by_action() {
  local ops_file="$1"
  local action="$2"
  awk -F'\t' -v a="$action" '$1==a{c++} END{print c+0}' "$ops_file"
}

syncctl_write_plan_json() {
  local plan_json="$1"
  local plan_id="$2"
  local direction="$3"
  local mode="$4"
  local platform="$5"
  local scope="$6"
  local skills_csv="$7"
  local tasks_file="$8"
  local ops_file="$9"
  local token="${10}"

  local created_at
  created_at="$(syncctl_now_iso)"
  local add_count update_count delete_count skip_count
  add_count="$(syncctl_count_ops_by_action "$ops_file" add)"
  update_count="$(syncctl_count_ops_by_action "$ops_file" update)"
  delete_count="$(syncctl_count_ops_by_action "$ops_file" delete)"
  skip_count="$(syncctl_count_ops_by_action "$ops_file" skip)"

  python3 - "$plan_json" "$plan_id" "$created_at" "$direction" "$mode" "$platform" "$scope" "$skills_csv" "$tasks_file" "$ops_file" "$token" "$add_count" "$update_count" "$delete_count" "$skip_count" <<'PY'
import csv
import json
import sys

(
    plan_path,
    plan_id,
    created_at,
    direction,
    mode,
    platform,
    scope,
    skills_csv,
    tasks_file,
    ops_file,
    token,
    add_count,
    update_count,
    delete_count,
    skip_count,
) = sys.argv[1:]

skills = [s for s in skills_csv.split(",") if s]

with open(tasks_file, encoding="utf-8") as f:
    task_rows = list(csv.reader(f, delimiter="\t"))

with open(ops_file, encoding="utf-8") as f:
    op_rows = list(csv.reader(f, delimiter="\t"))

plan = {
    "plan_id": plan_id,
    "created_at": created_at,
    "direction": direction,
    "mode": mode,
    "platform": platform,
    "scope": scope,
    "skills": skills,
    "approve_token": token,
    "files": {
        "tasks_tsv": tasks_file,
        "ops_tsv": ops_file,
    },
    "summary": {
        "add": int(add_count),
        "update": int(update_count),
        "delete": int(delete_count),
        "skip": int(skip_count),
        "task_count": len(task_rows),
        "op_count": len(op_rows),
    },
}

with open(plan_path, "w", encoding="utf-8") as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

syncctl_read_plan_meta_tsv() {
  local plan_json="$1"
  python3 - "$plan_json" <<'PY'
import json
import sys

plan_path = sys.argv[1]
with open(plan_path, encoding="utf-8") as f:
    p = json.load(f)

print(
    "\t".join(
        [
            p.get("approve_token", ""),
            p.get("direction", ""),
            p.get("mode", ""),
            p.get("files", {}).get("tasks_tsv", ""),
            p.get("files", {}).get("ops_tsv", ""),
            str(p.get("summary", {}).get("delete", 0)),
        ]
    )
)
PY
}

syncctl_print_check_text() {
  local plan_id="$1"
  local token="$2"
  local plan_json="$3"
  local ops_file="$4"

  local add_count update_count delete_count skip_count
  add_count="$(syncctl_count_ops_by_action "$ops_file" add)"
  update_count="$(syncctl_count_ops_by_action "$ops_file" update)"
  delete_count="$(syncctl_count_ops_by_action "$ops_file" delete)"
  skip_count="$(syncctl_count_ops_by_action "$ops_file" skip)"

  echo "[syncctl][check] plan_id=$plan_id"
  echo "[syncctl][check] approve_token=$token"
  echo "[syncctl][check] plan_file=$plan_json"
  echo "[syncctl][summary] add=$add_count update=$update_count delete=$delete_count skip=$skip_count"

  awk -F'\t' '
    {
      key=$1":"$2
      c[key]++
    }
    END {
      for (k in c) {
        split(k,a,":")
        printf("[syncctl][ops] action=%s platform=%s count=%d\n", a[1], a[2], c[k])
      }
    }
  ' "$ops_file" | sort
}

syncctl_print_check_json() {
  local plan_json="$1"
  cat "$plan_json"
}

syncctl_is_safe_managed_path() {
  local path="$1"
  local codex_home="${CODEX_HOME:-$HOME/.codex}"
  local claude_home="${CLAUDE_HOME:-$HOME/.claude}"
  local hermes_home="${HERMES_HOME:-$HOME/.hermes}"

  case "$path" in
    "$SYNCCTL_REPO_ROOT"|"$SYNCCTL_REPO_ROOT"/*) return 0 ;;
    "$HOME/.codex"|"$HOME/.codex"/*) return 0 ;;
    "$HOME/.claude"|"$HOME/.claude"/*) return 0 ;;
    "$HOME/.hermes"|"$HOME/.hermes"/*) return 0 ;;
    "$codex_home"|"$codex_home"/*) return 0 ;;
    "$claude_home"|"$claude_home"/*) return 0 ;;
    "$hermes_home"|"$hermes_home"/*) return 0 ;;
    *) return 1 ;;
  esac
}

syncctl_parse_excludes_to_args() {
  local excludes="$1"
  local out_file="$2"

  : > "$out_file"
  [ -n "$excludes" ] || return 0

  local oldifs="$IFS"
  IFS='|'
  # shellcheck disable=SC2086
  set -- $excludes
  IFS="$oldifs"

  local ex
  for ex in "$@"; do
    [ -n "$ex" ] || continue
    printf '%s\n' "$ex" >> "$out_file"
  done
}

syncctl_should_use_delete_flag() {
  local delete_policy="$1"
  local allow_delete="$2"

  case "$delete_policy" in
    always) return 0 ;;
    allow)
      [ "$allow_delete" = "true" ]
      return
      ;;
    *) return 1 ;;
  esac
}
