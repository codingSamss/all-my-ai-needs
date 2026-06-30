#!/bin/bash

set -euo pipefail

syncctl_adapter_claude_collect_tasks() {
  local direction="$1"
  local scope="$2"
  local tasks_file="$3"

  local platform="claude"
  local repo_root="$SYNCCTL_REPO_ROOT/platforms/claude"
  local local_root="${CLAUDE_HOME:-$HOME/.claude}"

  local base_excludes=".gitkeep|__pycache__/|*.pyc|*.pyo|.DS_Store"
  local skill_runtime_excludes="/.gitignore|/README.md|/setup.sh|/skill.config.json|/runtime.yaml|/agents/"

  if syncctl_scope_includes "$scope" "skills"; then
    local skill_dir skill_name src dst excludes delete_policy task_id
    for skill_dir in "$repo_root/skills"/*; do
      [ -d "$skill_dir" ] || continue
      skill_name="$(basename "$skill_dir")"
      if ! syncctl_skill_selected "$skill_name" "$skill_name"; then
        continue
      fi

      if [ "$direction" = "repo-to-local" ]; then
        src="$repo_root/skills/$skill_name"
        dst="$local_root/skills/$skill_name"
        delete_policy="always"
      else
        src="$local_root/skills/$skill_name"
        dst="$repo_root/skills/$skill_name"
        delete_policy="allow"
      fi

      excludes="$base_excludes|$skill_runtime_excludes"
      if [ "$skill_name" = "bird-twitter" ]; then
        excludes="$excludes|/vendor/"
      fi

      task_id="$(syncctl_next_task_id)"
      if [ ! -d "$src" ]; then
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "skip" "-" "-" "never" "" "claude skill/$skill_name" "source_missing:$src"
      else
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "rsync_dir" "$src" "$dst" "$delete_policy" "$excludes" "claude skill/$skill_name" ""
      fi

      if [ "$direction" = "repo-to-local" ]; then
        local noise
        for noise in .gitignore README.md setup.sh skill.config.json runtime.yaml; do
          task_id="$(syncctl_next_task_id)"
          syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "remove_path" "-" "$dst/$noise" "always" "" "claude skill/$skill_name cleanup" "runtime_noise"
        done

        task_id="$(syncctl_next_task_id)"
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "remove_path" "-" "$dst/agents" "always" "" "claude skill/$skill_name cleanup" "runtime_agents"

        if [ "$skill_name" = "bird-twitter" ]; then
          task_id="$(syncctl_next_task_id)"
          syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "remove_path" "-" "$dst/vendor" "always" "" "claude skill/$skill_name cleanup" "repo_only_vendor"
        fi
      fi
    done
  fi

  if syncctl_scope_includes "$scope" "root"; then
    local rel src dst task_id
    for rel in hooks scripts agents; do
      if [ "$direction" = "repo-to-local" ]; then
        src="$repo_root/$rel"
        dst="$local_root/$rel"
      else
        src="$local_root/$rel"
        dst="$repo_root/$rel"
      fi

      task_id="$(syncctl_next_task_id)"
      if [ ! -d "$src" ]; then
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "$rel" "skip" "-" "-" "never" "" "claude root/$rel" "source_missing:$src"
      else
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "$rel" "rsync_dir" "$src" "$dst" "never" "$base_excludes" "claude root/$rel" ""
      fi
    done

    if [ "$direction" = "repo-to-local" ]; then
      src="$repo_root/CLAUDE.md"
      dst="$local_root/CLAUDE.md"
    else
      src="$local_root/CLAUDE.md"
      dst="$repo_root/CLAUDE.md"
    fi
    task_id="$(syncctl_next_task_id)"
    if [ ! -f "$src" ]; then
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "CLAUDE.md" "skip" "-" "-" "never" "" "claude root/CLAUDE.md" "source_missing:$src"
    else
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "CLAUDE.md" "rsync_file" "$src" "$dst" "never" "$base_excludes" "claude root/CLAUDE.md" ""
    fi
  fi

  if syncctl_scope_includes "$scope" "config"; then
    local task_id
    task_id="$(syncctl_next_task_id)"
    syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "config" ".mcp.json" "skip" "-" "-" "never" "" "claude mcp config" "check_only_no_auto_merge"
  fi
}
