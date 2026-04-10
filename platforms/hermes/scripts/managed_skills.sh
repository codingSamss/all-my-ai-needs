#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PLATFORM_ROOT/../.." && pwd)"
CODEX_SKILLS_ROOT="$REPO_ROOT/platforms/codex/skills"
HERMES_REPO_SKILLS_ROOT="$PLATFORM_ROOT/skills"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
HERMES_LOCAL_SKILLS_ROOT="$HERMES_HOME_DIR/skills"
EXTRA_SKILLS_FILE="$PLATFORM_ROOT/managed-extra-skills.txt"
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
  - 默认按 Codex 同名 skill 推导 Hermes 受管集合
  - Hermes-only 例外项从 platforms/hermes/managed-extra-skills.txt 读取
  - 只做检查，不会执行同步
USAGE
}

write_codex_names() {
  find "$CODEX_SKILLS_ROOT" -mindepth 1 -maxdepth 1 -type d \
    -exec basename {} \; | sort -u > "$TMP_DIR/codex_names"
}

write_repo_hermes_rels() {
  find "$HERMES_REPO_SKILLS_ROOT" -mindepth 2 -maxdepth 2 -type d \
    | sed "s#^$HERMES_REPO_SKILLS_ROOT/##" \
    | sort > "$TMP_DIR/repo_hermes_rels"
}

write_local_hermes_rels() {
  if [ ! -d "$HERMES_LOCAL_SKILLS_ROOT" ]; then
    : > "$TMP_DIR/local_hermes_rels"
    return
  fi

  find "$HERMES_LOCAL_SKILLS_ROOT" -mindepth 2 -maxdepth 2 -type d \
    | sed "s#^$HERMES_LOCAL_SKILLS_ROOT/##" \
    | sort > "$TMP_DIR/local_hermes_rels"
}

write_extra_rels() {
  if [ ! -f "$EXTRA_SKILLS_FILE" ]; then
    : > "$TMP_DIR/extra_rels"
    return
  fi

  grep -Ev '^[[:space:]]*($|#)' "$EXTRA_SKILLS_FILE" | sort -u > "$TMP_DIR/extra_rels" || true
}

prepare_sets() {
  write_codex_names
  write_repo_hermes_rels
  write_local_hermes_rels
  write_extra_rels
}

is_codex_name() {
  local skill_name="$1"
  grep -Fxq "$skill_name" "$TMP_DIR/codex_names"
}

is_extra_rel() {
  local rel_path="$1"
  grep -Fxq "$rel_path" "$TMP_DIR/extra_rels"
}

emit_managed_repo_rels() {
  local rel_path=""
  local skill_name=""

  while IFS= read -r rel_path; do
    skill_name="${rel_path##*/}"
    if is_codex_name "$skill_name" || is_extra_rel "$rel_path"; then
      printf '%s\n' "$rel_path"
    fi
  done < "$TMP_DIR/repo_hermes_rels"
}

emit_managed_repo_rels_with_source() {
  local rel_path=""
  local skill_name=""

  while IFS= read -r rel_path; do
    skill_name="${rel_path##*/}"
    if is_codex_name "$skill_name"; then
      printf '%s\t%s\n' "$rel_path" "codex-same-name"
    elif is_extra_rel "$rel_path"; then
      printf '%s\t%s\n' "$rel_path" "hermes-extra"
    fi
  done < "$TMP_DIR/repo_hermes_rels"
}

emit_unmanaged_repo_rels() {
  local rel_path=""
  local skill_name=""

  while IFS= read -r rel_path; do
    skill_name="${rel_path##*/}"
    if ! is_codex_name "$skill_name" && ! is_extra_rel "$rel_path"; then
      printf '%s\n' "$rel_path"
    fi
  done < "$TMP_DIR/repo_hermes_rels"
}

emit_candidate_local_rels() {
  local rel_path=""
  local skill_name=""

  emit_managed_repo_rels | awk -F/ '{print $NF}' | sort -u > "$TMP_DIR/managed_repo_names"

  while IFS= read -r rel_path; do
    skill_name="${rel_path##*/}"
    if is_codex_name "$skill_name" && ! grep -Fxq "$skill_name" "$TMP_DIR/managed_repo_names"; then
      printf '%s\n' "$rel_path"
    fi
  done < "$TMP_DIR/local_hermes_rels"
}

show_diff_status() {
  local rel_path=""
  local repo_dir=""
  local local_dir=""
  local diff_output=""
  local has_diff="false"

  while IFS= read -r rel_path; do
    repo_dir="$HERMES_REPO_SKILLS_ROOT/$rel_path"
    local_dir="$HERMES_LOCAL_SKILLS_ROOT/$rel_path"

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
  done < <(emit_managed_repo_rels)

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
    emit_managed_repo_rels_with_source
    ;;
  status)
    prepare_sets
    print_section "Managed Repo Skills"
    emit_managed_repo_rels_with_source
    echo
    print_section "Repo vs Local Diff"
    show_diff_status
    echo
    print_section "Local Codex-Name Candidates Not In Repo"
    emit_candidate_local_rels || true
    echo
    print_section "Repo Paths Outside Current Rule"
    emit_unmanaged_repo_rels || true
    ;;
  candidates)
    prepare_sets
    emit_candidate_local_rels
    ;;
  unmanaged-repo)
    prepare_sets
    emit_unmanaged_repo_rels
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
