#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLATFORM_ROOT="$REPO_ROOT/platforms/codex"
SKILLS_SOURCE_ROOT="$PLATFORM_ROOT/skills"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
DRY_RUN="false"
SYNC_SKILLS="true"
SYNC_ROOT="true"
SYNC_CONFIG="false"
AUTO_YES="false"

MANAGED_ROOT_DIRS=(
  "agents"
  "hooks"
  "scripts"
  "rules"
  "bin"
)
MANAGED_ROOT_FILES=(
  "AGENTS.md"
)

usage() {
  cat <<'USAGE'
用法:
  ./scripts/sync_to_codex.sh
  ./scripts/sync_to_codex.sh --dry-run
  ./scripts/sync_to_codex.sh --yes
  ./scripts/sync_to_codex.sh --skills-only
  ./scripts/sync_to_codex.sh --root-only
  ./scripts/sync_to_codex.sh --sync-config
  ./scripts/sync_to_codex.sh --codex-home /path/to/.codex

说明:
  默认同步到：
  - platforms/codex/skills -> ~/.codex/skills
  - ~/.codex/{AGENTS.md,agents,hooks,scripts,rules,bin}
  - 默认不覆盖 ~/.codex/config.toml（可用 --sync-config 显式启用）

  目录内每个 skill 必须包含 SKILL.md
  skill 级 runtime.yaml 保留在 repo，不会下发到 ~/.codex/skills
  repo-only 备份资产（如 bird-twitter/vendor）不会下发到 ~/.codex/skills
  所有同步均为增量模式（保留目录外未托管内容）
  使用 --sync-config 同步 root/config.toml 时会保留本地 MCP 敏感配置（鉴权字段、env token/key）
  避免覆盖本机 secret
  覆盖确认支持交互；非交互默认跳过覆盖。可用 --yes 自动覆盖
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --codex-home)
      shift
      [ $# -gt 0 ] || { echo "[错误] --codex-home 缺少参数"; exit 1; }
      CODEX_HOME_DIR="$1"
      ;;
    --dry-run)
      DRY_RUN="true"
      ;;
    --yes)
      AUTO_YES="true"
      ;;
    --skills-only)
      SYNC_ROOT="false"
      ;;
    --root-only)
      SYNC_SKILLS="false"
      ;;
    --sync-config)
      SYNC_CONFIG="true"
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

if ! command -v rsync >/dev/null 2>&1; then
  echo "[错误] 未找到 rsync，无法执行镜像同步"
  exit 1
fi

if [ "$SYNC_SKILLS" != "true" ] && [ "$SYNC_ROOT" != "true" ]; then
  echo "[错误] 无可执行同步目标（skills/root 均被关闭）"
  exit 1
fi

if [ "$SYNC_SKILLS" = "true" ]; then
  # 严格校验：每个 skill 必须有 SKILL.md（Codex 官方要求）
  has_skill="false"
  for source_root in "$SKILLS_SOURCE_ROOT"; do
    [ -d "$source_root" ] || continue
    for skill_dir in "$source_root"/*; do
      [ -d "$skill_dir" ] || continue
      has_skill="true"
      if [ ! -f "$skill_dir/SKILL.md" ]; then
        echo "[错误] 缺少 SKILL.md: $skill_dir"
        exit 1
      fi
    done
  done

  if [ "$has_skill" != "true" ]; then
    echo "[错误] 未发现任何可同步 skill: $SKILLS_SOURCE_ROOT"
    exit 1
  fi
fi

base_rsync_args=(
  "-a"
  "--exclude" ".gitkeep"
  "--exclude" "__pycache__/"
  "--exclude" "*.pyc"
  "--exclude" "*.pyo"
  "--exclude" ".DS_Store"
)
skill_runtime_noise_files=(
  ".gitignore"
  "README.md"
  "setup.sh"
  "skill.config.json"
  "runtime.yaml"
)
skill_repo_only_subdirs=(
  "bird-twitter/vendor"
)
if [ "$DRY_RUN" = "true" ]; then
  base_rsync_args+=("--dry-run" "--itemize-changes")
fi

echo "=== Codex 平台同步 ==="
echo "源目录(Codex 平台): $PLATFORM_ROOT"
echo "目标目录(CODEX_HOME): $CODEX_HOME_DIR"

sync_dir_incremental() {
  local source_dir="$1"
  local target_dir="$2"
  local label="$3"
  local rsync_args=("${base_rsync_args[@]}")

  if [ ! -d "$source_dir" ]; then
    echo "[跳过] ${label}（源目录不存在）: $source_dir"
    return 0
  fi

  mkdir -p "$target_dir"
  echo "[同步] ${label}: $source_dir -> $target_dir"
  rsync "${rsync_args[@]}" "$source_dir"/ "$target_dir"/
}

sync_skills_incremental() {
  local source_root="$1"
  local target_root="$2"
  local skill_dir=""
  local skill_name=""
  local rsync_args=()
  local noise_file=""
  local repo_only_subdir=""
  local repo_only_rel=""
  local repo_only_target=""

  mkdir -p "$target_root"

  for skill_dir in "$source_root"/*; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    rsync_args=("${base_rsync_args[@]}")

    for noise_file in "${skill_runtime_noise_files[@]}"; do
      rsync_args+=("--exclude" "/$noise_file")
    done
    for repo_only_subdir in "${skill_repo_only_subdirs[@]}"; do
      if [[ "$repo_only_subdir" == "$skill_name/"* ]]; then
        repo_only_rel="${repo_only_subdir#"$skill_name/"}"
        rsync_args+=("--exclude" "/$repo_only_rel/")
      fi
    done

    echo "[同步] skill/$skill_name: $skill_dir -> $target_root/$skill_name"
    mkdir -p "$target_root/$skill_name"
    rsync "${rsync_args[@]}" "$skill_dir"/ "$target_root/$skill_name"/

    for noise_file in "${skill_runtime_noise_files[@]}"; do
      if [ -e "$target_root/$skill_name/$noise_file" ]; then
        if [ "$DRY_RUN" = "true" ]; then
          echo "[清理预览] skill/$skill_name 删除运行态噪音: $target_root/$skill_name/$noise_file"
        else
          rm -f "$target_root/$skill_name/$noise_file"
          echo "[清理] skill/$skill_name 删除运行态噪音: $target_root/$skill_name/$noise_file"
        fi
      fi
    done
    for repo_only_subdir in "${skill_repo_only_subdirs[@]}"; do
      if [[ "$repo_only_subdir" == "$skill_name/"* ]]; then
        repo_only_rel="${repo_only_subdir#"$skill_name/"}"
        repo_only_target="$target_root/$skill_name/$repo_only_rel"
        if [ -e "$repo_only_target" ]; then
          if [ "$DRY_RUN" = "true" ]; then
            echo "[清理预览] skill/$skill_name 删除 repo-only 目录: $repo_only_target"
          else
            rm -rf "$repo_only_target"
            echo "[清理] skill/$skill_name 删除 repo-only 目录: $repo_only_target"
          fi
        fi
      fi
    done
  done
}

extract_mcp_sensitive_lines() {
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
        # 不回填占位符，避免“占位符覆盖真实值”的倒灌
        if (match($0, /=[[:space:]]*"<[^"]+>"/)) next
        print section, key, $0
      }
    }
  ' "$config_file" > "$output_file"
}

restore_mcp_sensitive_lines() {
  local config_file="$1"
  local sensitive_file="$2"

  [ -f "$config_file" ] || return 0
  [ -s "$sensitive_file" ] || return 0

  local tmp_file
  tmp_file="$(mktemp)"

  awk -v sensitive_file="$sensitive_file" '
    BEGIN {
      FS = "\t"
      sep = "\034"
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
    function flush_missing(section,   idx, sk, key) {
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

sync_file_incremental() {
  local source_file="$1"
  local target_file="$2"
  local label="$3"
  local rsync_args=("${base_rsync_args[@]}")
  local local_mcp_sensitive_tmp=""

  if [ ! -f "$source_file" ]; then
    echo "[跳过] ${label}（源文件不存在）: $source_file"
    return 0
  fi

  mkdir -p "$(dirname "$target_file")"

  # 目标文件已存在且内容有差异时，需用户确认才覆盖
  if [ -f "$target_file" ] && ! diff -q "$source_file" "$target_file" >/dev/null 2>&1; then
    echo "[注意] ${label} 与本地版本存在差异："
    diff --color=auto "$target_file" "$source_file" || true
    if [ "$DRY_RUN" = "true" ]; then
      echo "[跳过] ${label}（dry-run 模式）"
      return 0
    fi

    if [ "$AUTO_YES" = "true" ]; then
      answer="y"
      echo "[确认] --yes 已启用，自动覆盖: $target_file"
    elif [ ! -t 0 ]; then
      echo "[跳过] ${label}（非交互环境，保留本地版本；可用 --yes 自动覆盖）"
      return 0
    else
      printf "[确认] 是否用仓库版本覆盖 %s？[y/N] " "$target_file"
      read -r answer || answer=""
    fi

    if [ "${answer:-}" != "y" ] && [ "${answer:-}" != "Y" ]; then
      echo "[跳过] ${label}（保留本地版本）"
      return 0
    fi
  elif [ -f "$target_file" ]; then
    echo "[跳过] ${label}（无变化）"
    return 0
  fi

  if [ "$label" = "root/config.toml" ] && [ -f "$target_file" ] && [ "$DRY_RUN" != "true" ]; then
    local_mcp_sensitive_tmp="$(mktemp)"
    extract_mcp_sensitive_lines "$target_file" "$local_mcp_sensitive_tmp"
  fi

  echo "[同步] ${label}: $source_file -> $target_file"
  rsync "${rsync_args[@]}" "$source_file" "$target_file"

  if [ -n "$local_mcp_sensitive_tmp" ]; then
    restore_mcp_sensitive_lines "$target_file" "$local_mcp_sensitive_tmp"
    if [ -s "$local_mcp_sensitive_tmp" ]; then
      echo "[保留] ${label} 本地 MCP 敏感配置已保留"
    fi
    rm -f "$local_mcp_sensitive_tmp"
  fi
}

if [ "$SYNC_SKILLS" = "true" ]; then
  sync_skills_incremental "$SKILLS_SOURCE_ROOT" "$CODEX_HOME_DIR/skills"
  skill_count="$([ -d "$SKILLS_SOURCE_ROOT" ] && find "$SKILLS_SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
  echo "技能数: $skill_count"
fi

if [ "$SYNC_ROOT" = "true" ]; then
  for rel_dir in "${MANAGED_ROOT_DIRS[@]}"; do
    sync_dir_incremental "$PLATFORM_ROOT/$rel_dir" "$CODEX_HOME_DIR/$rel_dir" "root/$rel_dir"
  done

  for rel_file in "${MANAGED_ROOT_FILES[@]}"; do
    sync_file_incremental "$PLATFORM_ROOT/$rel_file" "$CODEX_HOME_DIR/$rel_file" "root/$rel_file"
  done

  if [ "$SYNC_CONFIG" = "true" ]; then
    sync_file_incremental "$PLATFORM_ROOT/config.toml" "$CODEX_HOME_DIR/config.toml" "root/config.toml"
  else
    echo "[跳过] root/config.toml（默认不覆盖本机配置；可用 --sync-config 启用）"
  fi
fi

echo ""
if [ "$DRY_RUN" = "true" ]; then
  echo "预览完成（未写入目标目录）。"
else
  echo "同步完成（skills 与受管 root 配置已增量同步）。"
fi
