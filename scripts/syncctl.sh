#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# shellcheck source=scripts/lib/syncctl_common.sh
source "$SCRIPT_DIR/lib/syncctl_common.sh"
# shellcheck source=scripts/lib/syncctl_adapter_codex.sh
source "$SCRIPT_DIR/lib/syncctl_adapter_codex.sh"
# shellcheck source=scripts/lib/syncctl_adapter_claude.sh
source "$SCRIPT_DIR/lib/syncctl_adapter_claude.sh"
# shellcheck source=scripts/lib/syncctl_adapter_hermes.sh
source "$SCRIPT_DIR/lib/syncctl_adapter_hermes.sh"

SYNCCTL_SKILL_FILTERS=()
SYNCCTL_CHECK_SCRATCH=""

usage() {
  cat <<'USAGE'
用法:
  ./scripts/syncctl.sh check \
    --direction repo-to-local|local-to-repo \
    --platform all|codex|claude|hermes \
    --scope all|skills|root|config|cron|memory \
    [--skill <skill_or_relpath>]... \
    [--format text|json]

  ./scripts/syncctl.sh apply \
    --plan-id <plan_id> \
    --approve-token <token> \
    [--allow-delete]

说明:
  - 默认口径为 minimal（按平台运行目录规则过滤 repo-only 文件）。
  - check 只做检查，不写入 repo 受管文件。
  - apply 只执行 check 产出的计划（plan_id + approve_token 绑定）。
  - local->repo 默认禁删；仅在 --allow-delete 时执行删除。
  - 计划文件默认写入 /tmp/all-my-ai-needs-syncctl/plans/<plan_id>/。
USAGE
}

validate_direction() {
  case "$1" in
    repo-to-local|local-to-repo) ;;
    *) syncctl_die "--direction 仅支持 repo-to-local|local-to-repo" ;;
  esac
}

validate_platform() {
  case "$1" in
    all|codex|claude|hermes) ;;
    *) syncctl_die "--platform 仅支持 all|codex|claude|hermes" ;;
  esac
}

validate_scope() {
  case "$1" in
    all|skills|root|config|cron|memory) ;;
    *) syncctl_die "--scope 仅支持 all|skills|root|config|cron|memory" ;;
  esac
}

validate_format() {
  case "$1" in
    text|json) ;;
    *) syncctl_die "--format 仅支持 text|json" ;;
  esac
}

syncctl_collect_tasks() {
  local direction="$1"
  local platform="$2"
  local scope="$3"
  local tasks_file="$4"

  case "$platform" in
    all)
      syncctl_adapter_codex_collect_tasks "$direction" "$scope" "$tasks_file"
      syncctl_adapter_claude_collect_tasks "$direction" "$scope" "$tasks_file"
      syncctl_adapter_hermes_collect_tasks "$direction" "$scope" "$tasks_file"
      ;;
    codex)
      syncctl_adapter_codex_collect_tasks "$direction" "$scope" "$tasks_file"
      ;;
    claude)
      syncctl_adapter_claude_collect_tasks "$direction" "$scope" "$tasks_file"
      ;;
    hermes)
      syncctl_adapter_hermes_collect_tasks "$direction" "$scope" "$tasks_file"
      ;;
    *)
      syncctl_die "未知 platform: $platform"
      ;;
  esac
}

syncctl_record_rsync_ops_from_log() {
  local log_file="$1"
  local ops_file="$2"
  local platform="$3"
  local scope="$4"
  local target="$5"
  local kind="$6"
  local src="$7"
  local dst="$8"
  local delete_policy="$9"
  local label="${10}"

  local line tag path action req src_entry dst_entry rel
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    [ "$line" = "sending incremental file list" ] && continue

    case "$line" in
      *"rsync error"*)
        continue
        ;;
      *deleting\ *)
        path="${line#*deleting }"
        req="0"
        if [ "$delete_policy" = "allow" ]; then
          req="1"
        fi
        if [ "$kind" = "rsync_dir" ]; then
          rel="$path"
          src_entry="${src%/}/$path"
          dst_entry="${dst%/}/$path"
        else
          rel="$(basename "$dst")"
          src_entry="$src"
          dst_entry="$dst"
        fi
        syncctl_add_op "$ops_file" "delete" "$platform" "$scope" "$target" "$rel" "$src_entry" "$dst_entry" "$req" "$label"
        continue
        ;;
    esac

    tag="${line%% *}"
    path="${line#* }"
    [ "$tag" = "$line" ] && continue

    case "$tag" in
      .*) continue ;;
    esac

    local type_char
    type_char="$(printf '%s' "$tag" | cut -c2)"
    [ "$type_char" = "d" ] && continue

    [ "$path" = "./" ] && continue

    if printf '%s' "$tag" | grep -q '+++++++'; then
      action="add"
    else
      action="update"
    fi

    if [ "$kind" = "rsync_dir" ]; then
      rel="$path"
      src_entry="${src%/}/$path"
      dst_entry="${dst%/}/$path"
    else
      rel="$(basename "$dst")"
      src_entry="$src"
      dst_entry="$dst"
    fi

    syncctl_add_op "$ops_file" "$action" "$platform" "$scope" "$target" "$rel" "$src_entry" "$dst_entry" "0" "$label"
  done < "$log_file"
}

syncctl_check_rsync_task() {
  local task_id="$1"
  local platform="$2"
  local scope="$3"
  local target="$4"
  local kind="$5"
  local src="$6"
  local dst="$7"
  local delete_policy="$8"
  local excludes="$9"
  local label="${10}"
  local ops_file="${11}"

  if [ ! -e "$src" ]; then
    syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "-" "$src" "$dst" "0" "source_missing"
    return 0
  fi

  local use_delete="false"
  if [ "$delete_policy" = "always" ] || [ "$delete_policy" = "allow" ]; then
    use_delete="true"
  fi

  local exclude_tmp
  exclude_tmp="$(mktemp)"
  syncctl_parse_excludes_to_args "$excludes" "$exclude_tmp"

  local -a rsync_args
  rsync_args=(-ainci)
  if [ "$use_delete" = "true" ]; then
    rsync_args+=(--delete)
  fi

  local ex
  while IFS= read -r ex; do
    [ -n "$ex" ] || continue
    rsync_args+=(--exclude "$ex")
  done < "$exclude_tmp"

  local real_dst="$dst"
  local check_dst="$dst"
  if [ "$kind" = "rsync_dir" ]; then
    if [ ! -d "$dst" ]; then
      check_dst="$SYNCCTL_CHECK_SCRATCH/$task_id-dst"
      mkdir -p "$check_dst"
    fi
  else
    if [ ! -e "$dst" ]; then
      mkdir -p "$SYNCCTL_CHECK_SCRATCH/$task_id-file"
      check_dst="$SYNCCTL_CHECK_SCRATCH/$task_id-file/$(basename "$dst")"
    fi
  fi

  local src_arg dst_arg
  if [ "$kind" = "rsync_dir" ]; then
    src_arg="${src%/}/"
    dst_arg="${check_dst%/}/"
  else
    src_arg="$src"
    dst_arg="$check_dst"
  fi

  local log_file
  log_file="$(mktemp)"
  rsync "${rsync_args[@]}" "$src_arg" "$dst_arg" > "$log_file" 2>/dev/null || true
  syncctl_record_rsync_ops_from_log "$log_file" "$ops_file" "$platform" "$scope" "$target" "$kind" "$src" "$real_dst" "$delete_policy" "$label"

  rm -f "$exclude_tmp" "$log_file"
}

syncctl_check_remove_task() {
  local platform="$1"
  local scope="$2"
  local target="$3"
  local dst="$4"
  local delete_policy="$5"
  local label="$6"
  local ops_file="$7"

  [ -e "$dst" ] || return 0

  local req="0"
  if [ "$delete_policy" = "allow" ]; then
    req="1"
  fi

  syncctl_add_op "$ops_file" "delete" "$platform" "$scope" "$target" "$(basename "$dst")" "-" "$dst" "$req" "$label"
}

syncctl_check_codex_config_task() {
  local platform="$1"
  local scope="$2"
  local target="$3"
  local src="$4"
  local dst="$5"
  local label="$6"
  local ops_file="$7"

  if [ ! -f "$src" ]; then
    syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "-" "$src" "$dst" "0" "source_missing"
    return 0
  fi

  if [ ! -f "$dst" ]; then
    syncctl_add_op "$ops_file" "add" "$platform" "$scope" "$target" "config.toml" "$src" "$dst" "0" "$label"
    return 0
  fi

  if ! cmp -s "$src" "$dst"; then
    syncctl_add_op "$ops_file" "update" "$platform" "$scope" "$target" "config.toml" "$src" "$dst" "0" "$label"
  fi
}

syncctl_execute_check_tasks() {
  local tasks_file="$1"
  local ops_file="$2"

  local task_id platform direction scope target kind src dst delete_policy excludes label reason
  while IFS=$'\t' read -r task_id platform direction scope target kind src dst delete_policy excludes label reason; do
    [ -n "$task_id" ] || continue

    case "$kind" in
      rsync_dir|rsync_file)
        syncctl_check_rsync_task "$task_id" "$platform" "$scope" "$target" "$kind" "$src" "$dst" "$delete_policy" "$excludes" "$label" "$ops_file"
        ;;
      remove_path)
        syncctl_check_remove_task "$platform" "$scope" "$target" "$dst" "$delete_policy" "$label" "$ops_file"
        ;;
      codex_config)
        syncctl_check_codex_config_task "$platform" "$scope" "$target" "$src" "$dst" "$label" "$ops_file"
        ;;
      hermes_memory_entry)
        syncctl_check_hermes_memory_task "$platform" "$scope" "$target" "$src" "$dst" "$excludes" "$reason" "$ops_file"
        ;;
      skip)
        syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "-" "$src" "$dst" "0" "$reason"
        ;;
      *)
        syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "-" "$src" "$dst" "0" "unsupported_task_kind:$kind"
        ;;
    esac
  done < "$tasks_file"
}

syncctl_apply_rsync_task() {
  local kind="$1"
  local src="$2"
  local dst="$3"
  local delete_policy="$4"
  local excludes="$5"
  local allow_delete="$6"

  if [ ! -e "$src" ]; then
    return 0
  fi

  local -a rsync_args
  rsync_args=(-a)

  if syncctl_should_use_delete_flag "$delete_policy" "$allow_delete"; then
    rsync_args+=(--delete)
  fi

  local exclude_tmp
  exclude_tmp="$(mktemp)"
  syncctl_parse_excludes_to_args "$excludes" "$exclude_tmp"

  local ex
  while IFS= read -r ex; do
    [ -n "$ex" ] || continue
    rsync_args+=(--exclude "$ex")
  done < "$exclude_tmp"

  if [ "$kind" = "rsync_dir" ]; then
    mkdir -p "$dst"
    rsync "${rsync_args[@]}" "${src%/}/" "${dst%/}/"
  else
    mkdir -p "$(dirname "$dst")"
    rsync "${rsync_args[@]}" "$src" "$dst"
  fi

  rm -f "$exclude_tmp"
}

syncctl_apply_remove_task() {
  local dst="$1"
  local delete_policy="$2"
  local allow_delete="$3"

  [ -e "$dst" ] || return 0

  if [ "$delete_policy" = "allow" ] && [ "$allow_delete" != "true" ]; then
    return 0
  fi

  if ! syncctl_is_safe_managed_path "$dst"; then
    syncctl_die "拒绝删除非受管路径: $dst"
  fi

  rm -rf "$dst"
}

syncctl_execute_apply_tasks() {
  local tasks_file="$1"
  local allow_delete="$2"

  local task_id platform direction scope target kind src dst delete_policy excludes label reason
  while IFS=$'\t' read -r task_id platform direction scope target kind src dst delete_policy excludes label reason; do
    [ -n "$task_id" ] || continue

    case "$kind" in
      rsync_dir|rsync_file)
        syncctl_apply_rsync_task "$kind" "$src" "$dst" "$delete_policy" "$excludes" "$allow_delete"
        SYNCCTL_APPLIED_TASK_COUNT=$((SYNCCTL_APPLIED_TASK_COUNT + 1))
        ;;
      remove_path)
        syncctl_apply_remove_task "$dst" "$delete_policy" "$allow_delete"
        SYNCCTL_APPLIED_TASK_COUNT=$((SYNCCTL_APPLIED_TASK_COUNT + 1))
        ;;
      codex_config)
        if [ -f "$src" ]; then
          syncctl_codex_apply_config "$src" "$dst"
          SYNCCTL_APPLIED_TASK_COUNT=$((SYNCCTL_APPLIED_TASK_COUNT + 1))
        fi
        ;;
      hermes_memory_entry)
        if syncctl_apply_hermes_memory_task "$target" "$src" "$dst" "$excludes" "$reason"; then
          SYNCCTL_APPLIED_TASK_COUNT=$((SYNCCTL_APPLIED_TASK_COUNT + 1))
        else
          rc=$?
          if [ "$rc" -eq 3 ]; then
            SYNCCTL_SKIPPED_HASH_MISMATCH_COUNT=$((SYNCCTL_SKIPPED_HASH_MISMATCH_COUNT + 1))
          fi
          SYNCCTL_SKIPPED_TASK_COUNT=$((SYNCCTL_SKIPPED_TASK_COUNT + 1))
        fi
        ;;
      skip)
        SYNCCTL_SKIPPED_TASK_COUNT=$((SYNCCTL_SKIPPED_TASK_COUNT + 1))
        ;;
      *)
        SYNCCTL_SKIPPED_TASK_COUNT=$((SYNCCTL_SKIPPED_TASK_COUNT + 1))
        ;;
    esac
  done < "$tasks_file"
}

run_check() {
  local direction="$1"
  local platform="$2"
  local scope="$3"
  local format="$4"

  validate_direction "$direction"
  validate_platform "$platform"
  validate_scope "$scope"
  validate_format "$format"

  if [ "${#SYNCCTL_SKILL_FILTERS[@]}" -gt 0 ] && [ "$scope" = "all" ]; then
    scope="skills"
  fi

  local plan_id
  plan_id="$(syncctl_generate_plan_id)"
  local plan_dir="$SYNCCTL_PLAN_ROOT/$plan_id"
  mkdir -p "$plan_dir"

  local tasks_file="$plan_dir/tasks.tsv"
  local ops_file="$plan_dir/ops.tsv"
  : > "$tasks_file"
  : > "$ops_file"

  syncctl_collect_tasks "$direction" "$platform" "$scope" "$tasks_file"

  SYNCCTL_CHECK_SCRATCH="$(mktemp -d /tmp/syncctl-check.XXXXXX)"
  syncctl_execute_check_tasks "$tasks_file" "$ops_file"
  rm -rf "$SYNCCTL_CHECK_SCRATCH"

  local skills_csv=""
  if [ "${#SYNCCTL_SKILL_FILTERS[@]}" -gt 0 ]; then
    local f
    for f in "${SYNCCTL_SKILL_FILTERS[@]}"; do
      if [ -z "$skills_csv" ]; then
        skills_csv="$f"
      else
        skills_csv="$skills_csv,$f"
      fi
    done
  fi

  local token
  token="$(syncctl_compute_token "$direction" "minimal" "$tasks_file" "$ops_file")"

  local plan_json="$plan_dir/plan.json"
  syncctl_write_plan_json "$plan_json" "$plan_id" "$direction" "minimal" "$platform" "$scope" "$skills_csv" "$tasks_file" "$ops_file" "$token"

  if [ "$format" = "json" ]; then
    syncctl_print_check_json "$plan_json"
  else
    syncctl_print_check_text "$plan_id" "$token" "$plan_json" "$ops_file"
  fi
}

run_apply() {
  local plan_id="$1"
  local approve_token="$2"
  local allow_delete="$3"

  [ -n "$plan_id" ] || syncctl_die "apply 需要 --plan-id"
  [ -n "$approve_token" ] || syncctl_die "apply 需要 --approve-token"

  local plan_dir="$SYNCCTL_PLAN_ROOT/$plan_id"
  local plan_json="$plan_dir/plan.json"
  [ -f "$plan_json" ] || syncctl_die "未找到计划文件: $plan_json"

  local stored_token direction mode tasks_file ops_file _delete_count
  IFS=$'\t' read -r stored_token direction mode tasks_file ops_file _delete_count < <(syncctl_read_plan_meta_tsv "$plan_json")

  [ -f "$tasks_file" ] || syncctl_die "任务文件缺失: $tasks_file"
  [ -f "$ops_file" ] || syncctl_die "操作文件缺失: $ops_file"

  local recomputed
  recomputed="$(syncctl_compute_token "$direction" "$mode" "$tasks_file" "$ops_file")"

  [ "$stored_token" = "$recomputed" ] || syncctl_die "计划文件已变更（token 不匹配）"
  [ "$approve_token" = "$stored_token" ] || syncctl_die "approve token 无效"

  SYNCCTL_APPLIED_TASK_COUNT=0
  SYNCCTL_SKIPPED_TASK_COUNT=0
  SYNCCTL_SKIPPED_DELETE_COUNT=0
  SYNCCTL_SKIPPED_HASH_MISMATCH_COUNT=0
  if [ "$allow_delete" != "true" ]; then
    SYNCCTL_SKIPPED_DELETE_COUNT="$(awk -F'\t' '$1=="delete" && $8=="1"{c++} END{print c+0}' "$ops_file")"
  fi

  syncctl_execute_apply_tasks "$tasks_file" "$allow_delete"

  echo "[syncctl][apply] plan_id=$plan_id"
  echo "[syncctl][apply] direction=$direction"
  echo "[syncctl][apply] allow_delete=$allow_delete"
  echo "[syncctl][summary] applied_tasks=$SYNCCTL_APPLIED_TASK_COUNT skipped_tasks=$SYNCCTL_SKIPPED_TASK_COUNT skipped_delete=$SYNCCTL_SKIPPED_DELETE_COUNT skipped_hash_mismatch=$SYNCCTL_SKIPPED_HASH_MISMATCH_COUNT"

  if [ "$SYNCCTL_SKIPPED_DELETE_COUNT" -gt 0 ]; then
    echo "[syncctl][提示] 计划包含删除项，当前未开启 --allow-delete，删除已跳过。"
  fi
}

main() {
  [ $# -gt 0 ] || { usage; exit 1; }

  local command="$1"
  shift

  case "$command" in
    check)
      local direction=""
      local platform="all"
      local scope="all"
      local format="text"

      while [ $# -gt 0 ]; do
        case "$1" in
          --direction)
            shift
            [ $# -gt 0 ] || syncctl_die "--direction 缺少参数"
            direction="$1"
            ;;
          --platform)
            shift
            [ $# -gt 0 ] || syncctl_die "--platform 缺少参数"
            platform="$1"
            ;;
          --scope)
            shift
            [ $# -gt 0 ] || syncctl_die "--scope 缺少参数"
            scope="$1"
            ;;
          --skill)
            shift
            [ $# -gt 0 ] || syncctl_die "--skill 缺少参数"
            SYNCCTL_SKILL_FILTERS+=("$1")
            ;;
          --format)
            shift
            [ $# -gt 0 ] || syncctl_die "--format 缺少参数"
            format="$1"
            ;;
          -h|--help|help)
            usage
            exit 0
            ;;
          *)
            syncctl_die "check 未知参数: $1"
            ;;
        esac
        shift
      done

      [ -n "$direction" ] || syncctl_die "check 需要 --direction"
      run_check "$direction" "$platform" "$scope" "$format"
      ;;

    apply)
      local plan_id=""
      local approve_token=""
      local allow_delete="false"

      while [ $# -gt 0 ]; do
        case "$1" in
          --plan-id)
            shift
            [ $# -gt 0 ] || syncctl_die "--plan-id 缺少参数"
            plan_id="$1"
            ;;
          --approve-token)
            shift
            [ $# -gt 0 ] || syncctl_die "--approve-token 缺少参数"
            approve_token="$1"
            ;;
          --allow-delete)
            allow_delete="true"
            ;;
          -h|--help|help)
            usage
            exit 0
            ;;
          *)
            syncctl_die "apply 未知参数: $1"
            ;;
        esac
        shift
      done

      run_apply "$plan_id" "$approve_token" "$allow_delete"
      ;;

    -h|--help|help)
      usage
      ;;

    *)
      syncctl_die "未知命令: $command"
      ;;
  esac
}

main "$@"
