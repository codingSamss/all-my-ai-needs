#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_REPO_SKILLS_ROOT="$PLATFORM_ROOT/skills"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
HERMES_LOCAL_SKILLS_ROOT="$HERMES_HOME_DIR/skills"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

usage() {
  cat <<'USAGE'
用法:
  ./platforms/hermes/scripts/managed_skills.sh list
  ./platforms/hermes/scripts/managed_skills.sh status
  ./platforms/hermes/scripts/managed_skills.sh candidates
  ./platforms/hermes/scripts/managed_skills.sh unmanaged-repo

说明:
  - Hermes 受管集合仅来自 `hermes skills list --source local`
  - 不再按 Codex 同名推导，不再使用 managed-extra-skills.txt
  - 只做检查，不会执行同步或删除
USAGE
}

write_repo_hermes_rels() {
  if [ ! -d "$HERMES_REPO_SKILLS_ROOT" ]; then
    : > "$TMP_DIR/repo_hermes_rels"
    return
  fi

  while IFS= read -r dir_path; do
    if [ -f "$dir_path/SKILL.md" ]; then
      printf '%s\n' "${dir_path#"$HERMES_REPO_SKILLS_ROOT/"}"
    fi
  done < <(find "$HERMES_REPO_SKILLS_ROOT" -mindepth 2 -maxdepth 2 -type d | sort) > "$TMP_DIR/repo_hermes_rels"
}

write_local_hermes_rels_from_cli() {
  if ! command -v hermes >/dev/null 2>&1; then
    echo "[错误] 未找到 hermes 命令，无法读取 local skills" >&2
    exit 2
  fi

  hermes skills list --source local 2>/dev/null \
    | awk -F'│' '
      $0 ~ /^│/ {
        name=$2
        category=$3
        source=$4
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", category)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", source)
        if (source == "local" && name != "Name" && category != "Category" && category != "") {
          print category "/" name
        }
      }
    ' \
    | sort -u > "$TMP_DIR/local_hermes_rels"
}

prepare_sets() {
  write_repo_hermes_rels
  write_local_hermes_rels_from_cli
}

emit_local_with_source() {
  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    printf '%s\t%s\n' "$rel_path" "local-source"
  done < "$TMP_DIR/local_hermes_rels"
}

emit_local_not_in_repo() {
  comm -23 "$TMP_DIR/local_hermes_rels" "$TMP_DIR/repo_hermes_rels"
}

emit_repo_not_in_local() {
  comm -13 "$TMP_DIR/local_hermes_rels" "$TMP_DIR/repo_hermes_rels"
}

emit_intersection_rels() {
  comm -12 "$TMP_DIR/local_hermes_rels" "$TMP_DIR/repo_hermes_rels"
}

show_diff_status() {
  local rel_path=""
  local repo_dir=""
  local local_dir=""
  local diff_output=""
  local has_diff="false"

  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    repo_dir="$HERMES_REPO_SKILLS_ROOT/$rel_path"
    local_dir="$HERMES_LOCAL_SKILLS_ROOT/$rel_path"

    if [ ! -d "$repo_dir" ]; then
      printf 'MISSING_REPO\t%s\n' "$rel_path"
      has_diff="true"
      continue
    fi

    if [ ! -d "$local_dir" ]; then
      printf 'MISSING_LOCAL\t%s\n' "$rel_path"
      has_diff="true"
      continue
    fi

    diff_output="$(diff -qr \
      --exclude runtime.yaml \
      --exclude .DS_Store \
      "$repo_dir" "$local_dir" 2>/dev/null || true)"
    if [ -n "$diff_output" ]; then
      printf 'DIFF\t%s\n' "$rel_path"
      printf '%s\n' "$diff_output"
      printf '%s\n' '---'
      has_diff="true"
    fi
  done < <(emit_intersection_rels)

  if [ "$has_diff" != "true" ]; then
    echo "CLEAN"
  fi
}

print_section() {
  local title="$1"
  printf '== %s ==\n' "$title"
}

COMMAND="${1:-status}"

case "$COMMAND" in
  list)
    prepare_sets
    emit_local_with_source
    ;;
  status)
    prepare_sets
    print_section "Local Skills (source=local)"
    emit_local_with_source
    echo
    print_section "Repo vs Local Diff (Intersection)"
    show_diff_status
    echo
    print_section "Local Skills Not In Repo (Add Candidates)"
    emit_local_not_in_repo || true
    echo
    print_section "Repo Skills Not In Local (Remove Candidates / Manual Confirm)"
    emit_repo_not_in_local || true
    ;;
  candidates)
    prepare_sets
    emit_local_not_in_repo
    ;;
  unmanaged-repo)
    prepare_sets
    emit_repo_not_in_local
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "[错误] 未知命令: $COMMAND"
    usage
    exit 1
    ;;
esac
