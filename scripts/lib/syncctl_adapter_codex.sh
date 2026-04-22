#!/bin/bash

set -euo pipefail

syncctl_adapter_codex_collect_tasks() {
  local direction="$1"
  local scope="$2"
  local tasks_file="$3"

  local platform="codex"
  local repo_root="$SYNCCTL_REPO_ROOT/platforms/codex"
  local local_root="${CODEX_HOME:-$HOME/.codex}"

  local base_excludes=".gitkeep|__pycache__/|*.pyc|*.pyo|.DS_Store"
  local skill_noise_excludes="/.gitignore|/README.md|/setup.sh|/skill.config.json|/runtime.yaml"

  if syncctl_scope_includes "$scope" "skills"; then
    local skill_dir skill_name src dst excludes task_id
    for skill_dir in "$repo_root/skills"/*; do
      [ -d "$skill_dir" ] || continue
      skill_name="$(basename "$skill_dir")"
      if ! syncctl_skill_selected "$skill_name" "$skill_name"; then
        continue
      fi

      if [ "$direction" = "repo-to-local" ]; then
        src="$repo_root/skills/$skill_name"
        dst="$local_root/skills/$skill_name"
      else
        src="$local_root/skills/$skill_name"
        dst="$repo_root/skills/$skill_name"
      fi

      excludes="$base_excludes|$skill_noise_excludes"
      if [ "$skill_name" = "bird-twitter" ]; then
        excludes="$excludes|/vendor/"
      fi

      task_id="$(syncctl_next_task_id)"
      if [ ! -d "$src" ]; then
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "skip" "-" "-" "never" "" "codex skill/$skill_name" "source_missing:$src"
      else
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "rsync_dir" "$src" "$dst" "never" "$excludes" "codex skill/$skill_name" ""
      fi

      if [ "$direction" = "repo-to-local" ]; then
        local noise
        for noise in .gitignore README.md setup.sh skill.config.json runtime.yaml; do
          task_id="$(syncctl_next_task_id)"
          syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "remove_path" "-" "$dst/$noise" "always" "" "codex skill/$skill_name cleanup" "runtime_noise"
        done

        if [ "$skill_name" = "bird-twitter" ]; then
          task_id="$(syncctl_next_task_id)"
          syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "skills" "$skill_name" "remove_path" "-" "$dst/vendor" "always" "" "codex skill/$skill_name cleanup" "repo_only_vendor"
        fi
      fi
    done
  fi

  if syncctl_scope_includes "$scope" "root"; then
    local rel src dst task_id
    for rel in agents hooks scripts rules bin; do
      if [ "$direction" = "repo-to-local" ]; then
        src="$repo_root/$rel"
        dst="$local_root/$rel"
      else
        src="$local_root/$rel"
        dst="$repo_root/$rel"
      fi

      task_id="$(syncctl_next_task_id)"
      if [ ! -d "$src" ]; then
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "$rel" "skip" "-" "-" "never" "" "codex root/$rel" "source_missing:$src"
      else
        syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "$rel" "rsync_dir" "$src" "$dst" "never" "$base_excludes" "codex root/$rel" ""
      fi
    done

    if [ "$direction" = "repo-to-local" ]; then
      src="$repo_root/AGENTS.md"
      dst="$local_root/AGENTS.md"
    else
      src="$local_root/AGENTS.md"
      dst="$repo_root/AGENTS.md"
    fi
    task_id="$(syncctl_next_task_id)"
    if [ ! -f "$src" ]; then
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "AGENTS.md" "skip" "-" "-" "never" "" "codex root/AGENTS.md" "source_missing:$src"
    else
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "root" "AGENTS.md" "rsync_file" "$src" "$dst" "never" "$base_excludes" "codex root/AGENTS.md" ""
    fi
  fi

  if syncctl_scope_includes "$scope" "config"; then
    local task_id
    task_id="$(syncctl_next_task_id)"
    if [ "$direction" = "repo-to-local" ]; then
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "config" "config.toml" "codex_config" "$repo_root/config.toml" "$local_root/config.toml" "never" "" "codex config.toml" "preserve_mcp_sensitive"
    else
      syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "config" "config.toml" "skip" "-" "-" "never" "" "codex config.toml" "local_to_repo_forbidden"
    fi
  fi
}

syncctl_codex_extract_mcp_sensitive_lines() {
  local config_file="$1"
  local output_file="$2"

  : > "$output_file"
  [ -f "$config_file" ] || return 0

  awk '
    BEGIN { OFS = "\t" }
    function is_mcp_base_section(s) { return s ~ /^\[mcp_servers\.[^]]+\]$/ && s !~ /\.env\]$/ }
    function is_mcp_env_section(s) { return s ~ /^\[mcp_servers\.[^]]+\.env\]$/ }
    function is_sensitive_base_key(k) {
      return k == "bearer_token_env_var" || k == "http_headers" || k == "env_http_headers" || k == "env" || k ~ /(token|secret|password|api[_-]?key|authorization)/
    }
    /^\[/ {
      section = $0
      in_base = is_mcp_base_section(section)
      in_env = is_mcp_env_section(section)
      next
    }
    !(in_base || in_env) { next }
    {
      line = $0
      sub(/^[[:space:]]*/, "", line)
      if (line !~ /^[A-Za-z0-9_.-]+[[:space:]]*=/) next
      key = line
      sub(/[[:space:]]*=.*/, "", key)
      key_lower = tolower(key)
      if (in_env || is_sensitive_base_key(key_lower)) {
        if (match($0, /=[[:space:]]*"<[^"]+>"/)) next
        print section, key, $0
      }
    }
  ' "$config_file" > "$output_file"
}

syncctl_codex_restore_mcp_sensitive_lines() {
  local config_file="$1"
  local sensitive_file="$2"

  [ -f "$config_file" ] || return 0
  [ -s "$sensitive_file" ] || return 0

  local tmp_file
  tmp_file="$(mktemp)"

  awk -v sensitive_file="$sensitive_file" '
    BEGIN {
      FS = "\t"
      while ((getline line < sensitive_file) > 0) {
        n = split(line, fields, FS)
        section = fields[1]
        key = fields[2]
        value = fields[3]
        if (n > 3) {
          for (i = 4; i <= n; i++) value = value FS fields[i]
        }
        if (section == "" || key == "" || value == "") continue
        preserve[section SUBSEP key] = value
        if (!(section SUBSEP key in ordered_seen)) {
          ordered[++ordered_count] = section SUBSEP key
          ordered_seen[section SUBSEP key] = 1
        }
        if (section ~ /^\[mcp_servers\.[^]]+\.env\]$/) {
          parent_section = section
          sub(/\.env\]$/, "]", parent_section)
          env_inline[parent_section SUBSEP key] = value
          if (!(parent_section SUBSEP key in env_ordered_seen)) {
            env_ordered[++env_ordered_count] = parent_section SUBSEP key
            env_ordered_seen[parent_section SUBSEP key] = 1
          }
        }
      }
      close(sensitive_file)
    }
    function flush_missing(section, idx, sk, key) {
      if (section == "") return
      for (idx = 1; idx <= ordered_count; idx++) {
        sk = ordered[idx]
        split(sk, parts, SUBSEP)
        if (parts[1] != section) continue
        key = parts[2]
        if (!(section SUBSEP key in emitted)) {
          print preserve[section SUBSEP key]
          emitted[section SUBSEP key] = 1
        }
      }
    }
    /^\[/ {
      flush_missing(current_section)
      current_section = $0
      print
      next
    }
    {
      if (current_section != "") {
        line = $0
        trimmed = line
        sub(/^[[:space:]]*/, "", trimmed)
        if (trimmed ~ /^[A-Za-z0-9_.-]+[[:space:]]*=/) {
          key = trimmed
          sub(/[[:space:]]*=.*/, "", key)

          if (key == "env") {
            changed = 0
            for (idx = 1; idx <= env_ordered_count; idx++) {
              sk = env_ordered[idx]
              split(sk, parts, SUBSEP)
              if (parts[1] != current_section) continue
              env_key = parts[2]
              before = line
              gsub(env_key "[[:space:]]*=[[:space:]]*\"[^\"]*\"", env_inline[sk], line)
              if (line != before) {
                emitted[sk] = 1
                changed = 1
              }
            }
            if (changed) {
              print line
              emitted[current_section SUBSEP key] = 1
              next
            }
          }

          if (current_section SUBSEP key in preserve) {
            print preserve[current_section SUBSEP key]
            emitted[current_section SUBSEP key] = 1
            next
          }
        }
      }
      print
    }
    END {
      flush_missing(current_section)
    }
  ' "$config_file" > "$tmp_file"

  mv "$tmp_file" "$config_file"
}

syncctl_codex_apply_config() {
  local source_file="$1"
  local target_file="$2"

  [ -f "$source_file" ] || return 0

  mkdir -p "$(dirname "$target_file")"

  local sensitive_tmp=""
  if [ -f "$target_file" ]; then
    sensitive_tmp="$(mktemp)"
    syncctl_codex_extract_mcp_sensitive_lines "$target_file" "$sensitive_tmp"
  fi

  cp "$source_file" "$target_file"

  if [ -n "$sensitive_tmp" ]; then
    syncctl_codex_restore_mcp_sensitive_lines "$target_file" "$sensitive_tmp"
    rm -f "$sensitive_tmp"
  fi
}
