#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_REPO_SKILLS_ROOT="$PLATFORM_ROOT/skills"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
HERMES_LOCAL_SKILLS_ROOT="$HERMES_HOME_DIR/skills"
HERMES_UPSTREAM_ROOT="$HERMES_HOME_DIR/hermes-agent"
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
  ./platforms/hermes/scripts/managed_skills.sh likely-custom
  ./platforms/hermes/scripts/managed_skills.sh official-review
  ./platforms/hermes/scripts/managed_skills.sh unmanaged-repo

说明:
  - Hermes 受管集合仅来自 `hermes skills list --source local`
  - 官方来源优先按 `hermes skills list --source builtin|hub` 建索引（失败回退到本地 manifest）
  - local 名称会回查 `~/.hermes/skills/**/SKILL.md` 解析真实路径（支持多级分类）
  - `candidates` 默认只排除 `upstream-mirror`（目录内容与 upstream 完全一致）
  - 其余类型（含 `upstream-superseded` / `upstream-catalog`）保留在候选中做人审，防止同名误杀
  - `likely-custom` 只输出更可能是自定义的候选（`custom-local` + `upstream-variant`）
  - `official-review` 输出带官方迹象的候选（`upstream-superseded` / `upstream-catalog` / `unknown`）
  - `unmanaged-repo` 只输出“本地磁盘缺失”的 repo 项（避免把 builtin/hub 误报为删除候选）
  - 不再按 Codex 同名推导，不再使用 managed-extra-skills.txt
  - 只做检查，不会执行同步或删除
USAGE
}

extract_skill_name_from_file() {
  local skill_file="$1"
  awk '
    BEGIN { in_frontmatter=0 }
    /^---$/ {
      in_frontmatter = !in_frontmatter
      next
    }
    in_frontmatter == 1 && $0 ~ /^name:[[:space:]]*/ {
      line = $0
      sub(/^name:[[:space:]]*/, "", line)
      gsub(/^["'"'"']|["'"'"']$/, "", line)
      print line
      exit
    }
  ' "$skill_file"
}

extract_skill_author_from_file() {
  local skill_file="$1"
  awk '
    BEGIN { in_frontmatter=0 }
    /^---$/ {
      in_frontmatter = !in_frontmatter
      next
    }
    in_frontmatter == 1 && $0 ~ /^author:[[:space:]]*/ {
      line = $0
      sub(/^author:[[:space:]]*/, "", line)
      gsub(/^["'"'"']|["'"'"']$/, "", line)
      print line
      exit
    }
  ' "$skill_file"
}

write_repo_hermes_rels() {
  if [ ! -d "$HERMES_REPO_SKILLS_ROOT" ]; then
    : > "$TMP_DIR/repo_hermes_rels"
    return
  fi

  while IFS= read -r skill_file; do
    dir_path="$(dirname "$skill_file")"
    printf '%s\n' "${dir_path#"$HERMES_REPO_SKILLS_ROOT/"}"
  done < <(find "$HERMES_REPO_SKILLS_ROOT" -type f -name SKILL.md | sort) > "$TMP_DIR/repo_hermes_rels"
}

write_local_cli_rows() {
  if ! command -v hermes >/dev/null 2>&1; then
    echo "[错误] 未找到 hermes 命令，无法读取 local skills" >&2
    exit 2
  fi

  COLUMNS=400 hermes skills list --source local 2>/dev/null \
    | awk -F'│' '
      $0 ~ /^│/ {
        name=$2
        category=$3
        source=$4
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", category)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", source)
        if (source == "local" && name != "Name" && category != "Category" && category != "") {
          printf "%s\t%s\t%s\n", name, category, source
        }
      }
    ' \
    | sort -u > "$TMP_DIR/local_cli_rows"
}

write_names_from_hermes_source() {
  local source_name="$1"
  local out_file="$2"
  : > "$out_file"

  if ! command -v hermes >/dev/null 2>&1; then
    return
  fi

  if ! COLUMNS=400 hermes skills list --source "$source_name" 2>/dev/null \
    | awk -F'│' -v wanted="$source_name" '
      $0 ~ /^│/ {
        name=$2
        source=$4
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", source)
        if (name != "" && name != "Name" && source == wanted) {
          print name
        }
      }
    ' \
    | sort -u > "$out_file"; then
    : > "$out_file"
  fi
}

write_official_name_indexes() {
  : > "$TMP_DIR/official_builtin_names"
  : > "$TMP_DIR/official_hub_names"

  write_names_from_hermes_source "builtin" "$TMP_DIR/official_builtin_names"
  write_names_from_hermes_source "hub" "$TMP_DIR/official_hub_names"

  if [ ! -s "$TMP_DIR/official_builtin_names" ] && [ -f "$HERMES_LOCAL_SKILLS_ROOT/.bundled_manifest" ]; then
    awk -F':' 'NF>=1 { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1); if ($1!="") print $1 }' \
      "$HERMES_LOCAL_SKILLS_ROOT/.bundled_manifest" \
      | sort -u > "$TMP_DIR/official_builtin_names"
  fi
}

write_local_name_index() {
  : > "$TMP_DIR/local_name_index"
  if [ ! -d "$HERMES_LOCAL_SKILLS_ROOT" ]; then
    return
  fi

  while IFS= read -r skill_file; do
    local_name="$(extract_skill_name_from_file "$skill_file")"
    [ -n "${local_name:-}" ] || continue
    local_rel="$(dirname "$skill_file")"
    local_rel="${local_rel#"$HERMES_LOCAL_SKILLS_ROOT/"}"
    printf '%s\t%s\n' "$local_name" "$local_rel"
  done < <(
    find "$HERMES_LOCAL_SKILLS_ROOT" \
      -path "$HERMES_LOCAL_SKILLS_ROOT/.hub" -prune -o \
      -type f -name SKILL.md -print | sort
  ) | sort -u > "$TMP_DIR/local_name_index"
}

resolve_local_rel_from_name_and_category() {
  local skill_name="$1"
  local skill_category="$2"
  local matches=""
  local selected=""

  matches="$(awk -F'\t' -v n="$skill_name" '$1==n {print $2}' "$TMP_DIR/local_name_index" || true)"

  if [ -z "$matches" ]; then
    return 1
  fi

  if [ "$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')" -eq 1 ]; then
    printf '%s\n' "$matches"
    return 0
  fi

  selected="$(printf '%s\n' "$matches" | awk -F'/' -v c="$skill_category" '$1==c {print $0}' | head -n 1)"
  if [ -n "$selected" ]; then
    printf '%s\n' "$selected"
    return 0
  fi

  printf '%s\n' "$matches" | head -n 1
}

write_local_hermes_rels_from_cli() {
  : > "$TMP_DIR/local_hermes_rels"
  : > "$TMP_DIR/local_cli_unresolved"

  while IFS=$'\t' read -r name category source; do
    [ -n "${name:-}" ] || continue
    rel_path="$(resolve_local_rel_from_name_and_category "$name" "$category" || true)"
    if [ -n "$rel_path" ]; then
      printf '%s\n' "$rel_path"
    else
      printf '%s\t%s\n' "$category" "$name" >> "$TMP_DIR/local_cli_unresolved"
    fi
  done < "$TMP_DIR/local_cli_rows" | sort -u > "$TMP_DIR/local_hermes_rels"
}

lookup_official_source_by_name() {
  local skill_name="$1"
  if awk -v n="$skill_name" '$0==n {found=1; exit} END {exit(found?0:1)}' "$TMP_DIR/official_builtin_names"; then
    printf 'builtin\n'
    return
  fi
  if awk -v n="$skill_name" '$0==n {found=1; exit} END {exit(found?0:1)}' "$TMP_DIR/official_hub_names"; then
    printf 'hub\n'
    return
  fi
  printf 'none\n'
}

write_upstream_name_index() {
  : > "$TMP_DIR/upstream_name_index"
  for upstream_root in "$HERMES_UPSTREAM_ROOT/skills" "$HERMES_UPSTREAM_ROOT/optional-skills"; do
    [ -d "$upstream_root" ] || continue
    while IFS= read -r skill_file; do
      upstream_name="$(extract_skill_name_from_file "$skill_file")"
      [ -n "${upstream_name:-}" ] || continue
      upstream_dir="$(dirname "$skill_file")"
      printf '%s\t%s\n' "$upstream_name" "$upstream_dir"
    done < <(find "$upstream_root" -type f -name SKILL.md | sort)
  done | sort -u > "$TMP_DIR/upstream_name_index"
}

write_upstream_superseded_name_index() {
  : > "$TMP_DIR/upstream_superseded_name_index"
  for upstream_root in "$HERMES_UPSTREAM_ROOT/skills" "$HERMES_UPSTREAM_ROOT/optional-skills"; do
    [ -d "$upstream_root" ] || continue
    while IFS= read -r skill_file; do
      upstream_dir="$(dirname "$skill_file")"

      # Frontmatter: supersedes: [a, b]
      while IFS= read -r old_name; do
        [ -n "$old_name" ] || continue
        printf '%s\t%s\n' "$old_name" "$upstream_dir"
      done < <(
        awk '
          BEGIN { in_frontmatter=0 }
          /^---$/ { in_frontmatter=!in_frontmatter; next }
          in_frontmatter == 1 && $0 ~ /^supersedes:[[:space:]]*\[/ {
            line = $0
            sub(/^supersedes:[[:space:]]*\[/, "", line)
            sub(/\][[:space:]]*$/, "", line)
            n = split(line, arr, /,/)
            for (i=1; i<=n; i++) {
              item = arr[i]
              gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
              gsub(/^["'"'"']|["'"'"']$/, "", item)
              if (item != "") print item
            }
          }
        ' "$skill_file"
      )

      # Body patterns: "replaces the older `xxx` skill", "supersedes the old `xxx` skill"
      while IFS= read -r old_name; do
        [ -n "$old_name" ] || continue
        printf '%s\t%s\n' "$old_name" "$upstream_dir"
      done < <(
        perl -ne '
          while (/replaces\s+the\s+older\s+`([a-z0-9-]+)`\s+skill/ig) { print "$1\n" }
          while (/supersedes\s+the\s+old\s+`([a-z0-9-]+)`\s+skill/ig) { print "$1\n" }
        ' "$skill_file" | sort -u
      )
    done < <(find "$upstream_root" -type f -name SKILL.md | sort)
  done | sort -u > "$TMP_DIR/upstream_superseded_name_index"
}

same_dir_content() {
  local dir_a="$1"
  local dir_b="$2"
  diff -qr \
    --exclude runtime.yaml \
    --exclude .DS_Store \
    "$dir_a" "$dir_b" >/dev/null 2>&1
}

write_local_provenance() {
  : > "$TMP_DIR/local_provenance"
  : > "$TMP_DIR/local_official_source"
  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    local_dir="$HERMES_LOCAL_SKILLS_ROOT/$rel_path"
    local_skill_file="$local_dir/SKILL.md"
    if [ ! -f "$local_skill_file" ]; then
      printf '%s\t%s\t%s\n' "$rel_path" "unknown" "missing-skill-md" >> "$TMP_DIR/local_provenance"
      printf '%s\t%s\n' "$rel_path" "none" >> "$TMP_DIR/local_official_source"
      continue
    fi

    local_name="$(extract_skill_name_from_file "$local_skill_file")"
    local_author="$(extract_skill_author_from_file "$local_skill_file")"
    if [ -z "${local_name:-}" ]; then
      printf '%s\t%s\t%s\n' "$rel_path" "unknown" "missing-name" >> "$TMP_DIR/local_provenance"
      printf '%s\t%s\n' "$rel_path" "none" >> "$TMP_DIR/local_official_source"
      continue
    fi
    official_source="$(lookup_official_source_by_name "$local_name")"
    printf '%s\t%s\n' "$rel_path" "$official_source" >> "$TMP_DIR/local_official_source"

    upstream_dirs="$(awk -F'\t' -v n="$local_name" '$1==n {print $2}' "$TMP_DIR/upstream_name_index" || true)"
    if [ -z "$upstream_dirs" ]; then
      superseded_by_dirs="$(awk -F'\t' -v n="$local_name" '$1==n {print $2}' "$TMP_DIR/upstream_superseded_name_index" || true)"
      if [ -n "$superseded_by_dirs" ]; then
        superseded_by="$(printf '%s\n' "$superseded_by_dirs" | head -n 1)"
        printf '%s\t%s\t%s\n' "$rel_path" "upstream-superseded" "$superseded_by" >> "$TMP_DIR/local_provenance"
        continue
      fi
      if [ "${local_author:-}" = "Orchestra Research" ]; then
        printf '%s\t%s\t%s\n' "$rel_path" "upstream-catalog" "orchestra-author-no-local-upstream-copy" >> "$TMP_DIR/local_provenance"
        continue
      fi
      printf '%s\t%s\t%s\n' "$rel_path" "custom-local" "no-upstream-name-match" >> "$TMP_DIR/local_provenance"
      continue
    fi

    mirror_hit=""
    while IFS= read -r upstream_dir; do
      [ -n "$upstream_dir" ] || continue
      if same_dir_content "$local_dir" "$upstream_dir"; then
        mirror_hit="$upstream_dir"
        break
      fi
    done <<< "$upstream_dirs"

    if [ -n "$mirror_hit" ]; then
      printf '%s\t%s\t%s\n' "$rel_path" "upstream-mirror" "$mirror_hit" >> "$TMP_DIR/local_provenance"
    else
      printf '%s\t%s\t%s\n' "$rel_path" "upstream-variant" "name-match-diff-content" >> "$TMP_DIR/local_provenance"
    fi
  done < "$TMP_DIR/local_hermes_rels"
}

lookup_provenance_class() {
  local rel_path="$1"
  awk -F'\t' -v r="$rel_path" '$1==r {print $2; exit}' "$TMP_DIR/local_provenance"
}

lookup_official_source_by_rel() {
  local rel_path="$1"
  awk -F'\t' -v r="$rel_path" '$1==r {print $2; exit}' "$TMP_DIR/local_official_source"
}

build_official_hint() {
  local rel_path="$1"
  local provenance_class="$2"
  local official_source=""
  official_source="$(lookup_official_source_by_rel "$rel_path")"
  case "$official_source" in
    builtin) printf 'official-confirmed-builtin\n'; return ;;
    hub) printf 'official-confirmed-hub\n'; return ;;
  esac

  case "$provenance_class" in
    upstream-mirror|upstream-superseded|upstream-catalog)
      printf 'official-likely-upstream\n'
      ;;
    upstream-variant|custom-local)
      printf 'likely-custom\n'
      ;;
    *)
      printf 'review\n'
      ;;
  esac
}

write_candidate_sets() {
  comm -23 "$TMP_DIR/local_hermes_rels" "$TMP_DIR/repo_hermes_rels" > "$TMP_DIR/local_not_in_repo_raw"
  : > "$TMP_DIR/local_not_in_repo_candidates"
  : > "$TMP_DIR/local_not_in_repo_excluded_upstream"
  : > "$TMP_DIR/local_not_in_repo_likely_custom"
  : > "$TMP_DIR/local_not_in_repo_official_review"

  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    provenance_class="$(lookup_provenance_class "$rel_path")"
    if [ "$provenance_class" = "upstream-mirror" ]; then
      printf '%s\n' "$rel_path" >> "$TMP_DIR/local_not_in_repo_excluded_upstream"
      continue
    fi
    printf '%s\n' "$rel_path" >> "$TMP_DIR/local_not_in_repo_candidates"
    case "$provenance_class" in
      custom-local|upstream-variant)
        printf '%s\n' "$rel_path" >> "$TMP_DIR/local_not_in_repo_likely_custom"
        ;;
      *)
        printf '%s\n' "$rel_path" >> "$TMP_DIR/local_not_in_repo_official_review"
        ;;
    esac
  done < "$TMP_DIR/local_not_in_repo_raw"

  sort -u -o "$TMP_DIR/local_not_in_repo_candidates" "$TMP_DIR/local_not_in_repo_candidates"
  sort -u -o "$TMP_DIR/local_not_in_repo_excluded_upstream" "$TMP_DIR/local_not_in_repo_excluded_upstream"
  sort -u -o "$TMP_DIR/local_not_in_repo_likely_custom" "$TMP_DIR/local_not_in_repo_likely_custom"
  sort -u -o "$TMP_DIR/local_not_in_repo_official_review" "$TMP_DIR/local_not_in_repo_official_review"
}

write_repo_not_in_local_sets() {
  comm -13 "$TMP_DIR/local_hermes_rels" "$TMP_DIR/repo_hermes_rels" > "$TMP_DIR/repo_not_in_local_raw"
  : > "$TMP_DIR/repo_not_in_local_present_on_disk"
  : > "$TMP_DIR/repo_not_in_local_missing_on_disk"

  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    if [ -d "$HERMES_LOCAL_SKILLS_ROOT/$rel_path" ]; then
      printf '%s\n' "$rel_path" >> "$TMP_DIR/repo_not_in_local_present_on_disk"
    else
      printf '%s\n' "$rel_path" >> "$TMP_DIR/repo_not_in_local_missing_on_disk"
    fi
  done < "$TMP_DIR/repo_not_in_local_raw"

  sort -u -o "$TMP_DIR/repo_not_in_local_present_on_disk" "$TMP_DIR/repo_not_in_local_present_on_disk"
  sort -u -o "$TMP_DIR/repo_not_in_local_missing_on_disk" "$TMP_DIR/repo_not_in_local_missing_on_disk"
}

prepare_sets() {
  write_repo_hermes_rels
  write_local_cli_rows
  write_official_name_indexes
  write_local_name_index
  write_local_hermes_rels_from_cli
  write_upstream_name_index
  write_upstream_superseded_name_index
  write_local_provenance
  write_candidate_sets
  write_repo_not_in_local_sets
}

emit_local_with_source() {
  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    provenance_class="$(lookup_provenance_class "$rel_path")"
    [ -n "${provenance_class:-}" ] || provenance_class="unknown"
    official_hint="$(build_official_hint "$rel_path" "$provenance_class")"
    printf '%s\t%s\t%s\t%s\n' "$rel_path" "local-source" "$provenance_class" "$official_hint"
  done < "$TMP_DIR/local_hermes_rels"
}

emit_local_not_in_repo() {
  cat "$TMP_DIR/local_not_in_repo_candidates"
}

emit_local_not_in_repo_excluded_upstream() {
  cat "$TMP_DIR/local_not_in_repo_excluded_upstream"
}

emit_local_not_in_repo_likely_custom() {
  cat "$TMP_DIR/local_not_in_repo_likely_custom"
}

emit_local_not_in_repo_official_review() {
  cat "$TMP_DIR/local_not_in_repo_official_review"
}

emit_repo_not_in_local() {
  cat "$TMP_DIR/repo_not_in_local_missing_on_disk"
}

emit_repo_not_in_local_present_on_disk() {
  cat "$TMP_DIR/repo_not_in_local_present_on_disk"
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
    print_section "Local Skills Not In Repo (Add Candidates: non-mirror)"
    emit_local_not_in_repo || true
    echo
    print_section "Local Skills Not In Repo (Likely Custom)"
    emit_local_not_in_repo_likely_custom || true
    echo
    print_section "Local Skills Not In Repo (Official Review)"
    emit_local_not_in_repo_official_review || true
    echo
    print_section "Local Skills Not In Repo (Excluded by Policy)"
    emit_local_not_in_repo_excluded_upstream || true
    echo
    print_section "Repo Skills Not In Local Source (Present On Disk / Likely builtin-hub)"
    emit_repo_not_in_local_present_on_disk || true
    echo
    print_section "Repo Skills Missing On Local Disk (Remove Candidates / Manual Confirm)"
    emit_repo_not_in_local || true
    if [ -s "$TMP_DIR/local_cli_unresolved" ]; then
      echo
      print_section "Unresolved CLI Rows (Need Manual Check)"
      cat "$TMP_DIR/local_cli_unresolved"
    fi
    ;;
  candidates)
    prepare_sets
    emit_local_not_in_repo
    ;;
  likely-custom)
    prepare_sets
    emit_local_not_in_repo_likely_custom
    ;;
  official-review)
    prepare_sets
    emit_local_not_in_repo_official_review
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
