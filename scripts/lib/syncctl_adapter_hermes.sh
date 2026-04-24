#!/bin/bash

set -euo pipefail

# shellcheck source=scripts/lib/syncctl_hermes_memory.sh
source "$SYNCCTL_REPO_ROOT/scripts/lib/syncctl_hermes_memory.sh"

syncctl_adapter_hermes_list_local_source_rels() {
  local repo_skills_root="$1"
  rg -l --glob '**/runtime.yaml' '^source\s*:\s*local\s*$' "$repo_skills_root" 2>/dev/null \
    | while IFS= read -r runtime_file; do
        rel="${runtime_file#"$repo_skills_root/"}"
        rel="${rel%/runtime.yaml}"
        printf '%s\n' "$rel"
      done \
    | sort
}

syncctl_adapter_hermes_skill_match() {
  local rel="$1"
  local name
  name="$(basename "$rel")"
  syncctl_skill_selected "$name" "$rel"
}

syncctl_adapter_hermes_collect_tasks() {
  local direction="$1"
  local scope="$2"
  local tasks_file="$3"

  local platform="hermes"
  local repo_root="$SYNCCTL_REPO_ROOT/platforms/hermes"
  local repo_skills_root="$repo_root/skills"
  local repo_cron_root="$repo_root/cron"
  local local_root="${HERMES_HOME:-$HOME/.hermes}"
  local local_skills_root="$local_root/skills"
  local local_cron_root="$local_root/cron"

  local base_excludes=".gitkeep|__pycache__/|*.pyc|*.pyo|.DS_Store"

  if syncctl_scope_includes "$scope" "skills"; then
    local rel src dst task_id excludes
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      if ! syncctl_adapter_hermes_skill_match "$rel"; then
        continue
      fi

      if [ "$direction" = "repo-to-local" ]; then
        src="$repo_skills_root/$rel"
        dst="$local_skills_root/$rel"
      else
        src="$local_skills_root/$rel"
        dst="$repo_skills_root/$rel"
      fi

      excludes="$base_excludes|/runtime.yaml"
      task_id="$(syncctl_next_task_id)"
      if [ ! -d "$src" ]; then
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$rel" "skip" "-" "-" "never" "" "hermes skill/$rel" "source_missing:$src"
      else
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$rel" "rsync_dir" "$src" "$dst" "allow" "$excludes" "hermes skill/$rel" "source_local_managed"
      fi
    done < <(syncctl_adapter_hermes_list_local_source_rels "$repo_skills_root")
  fi

  if syncctl_scope_includes "$scope" "cron"; then
    local src dst task_id excludes
    if [ "$direction" = "repo-to-local" ]; then
      src="$repo_cron_root"
      dst="$local_cron_root"
    else
      src="$local_cron_root"
      dst="$repo_cron_root"
    fi

    excludes="$base_excludes|/output/|/.tick.lock|/jobs.json.bak-*"
    task_id="$(syncctl_next_task_id)"
    if [ ! -d "$src" ]; then
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "cron" "cron" "skip" "-" "-" "never" "" "hermes cron" "source_missing:$src"
    else
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "cron" "cron" "rsync_dir" "$src" "$dst" "allow" "$excludes" "hermes cron" "managed_cron"
    fi
  fi

  if syncctl_scope_includes "$scope" "config"; then
    local task_id
    task_id="$(syncctl_next_task_id)"
    syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "config" "config.template.yaml" "skip" "-" "-" "never" "" "hermes config" "check_only_use_sync_to_hermes"
  fi

  if syncctl_scope_includes "$scope" "memory"; then
    syncctl_hermes_memory_collect_tasks "$tasks_file" "$platform" "$direction" "$repo_root" "$local_root"
  fi
}
