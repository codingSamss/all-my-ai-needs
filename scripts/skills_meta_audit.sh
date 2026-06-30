#!/usr/bin/env bash
#
# skills_meta_audit.sh — 校验 platforms/<p>/skills.meta.yaml 与实际 skills/ 目录一致。
#
# 只读、无副作用。这是"万无一失"那一档：不做任何同步决策，只做确定性结构校验。
# 检查项：
#   [E] 目录 <-> manifest 一一对应（无多无漏）
#   [E] scope 取值合法（core | project | manual-only）
#   [E] 引用的 profile 均已在 profiles 段定义
#   [W] core / manual-only skill 携带了 profiles（应留空）
#   [W] 定义了但无任何成员的 profile
# 退出码：0 全部通过（可含 warning）；1 存在 error。

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
platforms=(codex claude)
valid_scopes=" core project manual-only "

errors=0
warnings=0
err()  { printf '  [E] %s\n' "$1"; errors=$((errors + 1)); }
warn() { printf '  [W] %s\n' "$1"; warnings=$((warnings + 1)); }

for p in "${platforms[@]}"; do
  meta="$repo_root/platforms/$p/skills.meta.yaml"
  skills_dir="$repo_root/platforms/$p/skills"
  printf '== platform: %s ==\n' "$p"

  if [[ ! -f "$meta" ]]; then err "缺少 manifest: $meta"; continue; fi
  if [[ ! -d "$skills_dir" ]]; then err "缺少目录: $skills_dir"; continue; fi

  # 已定义的 profile 名（profiles 段内的缩进键）
  defined_profiles="$(awk '
    /^profiles:/ { inp = 1; next }
    /^[a-zA-Z]/ && inp { inp = 0 }
    inp && /^[[:space:]]+[a-z0-9-]+:/ {
      k = $0; sub(/^[[:space:]]+/, "", k); sub(/:.*/, "", k); print k
    }
  ' "$meta" | sort -u)"

  # skills: 段内每行解析为 name|scope|profilesCSV
  manifest_rows="$(awk '
    /^skills:/ { ins = 1; next }
    /^[a-zA-Z]/ && ins { ins = 0 }
    ins && /^[[:space:]]+[a-zA-Z0-9_-]+:[[:space:]]*\{/ {
      name = $0; sub(/^[[:space:]]+/, "", name); sub(/:.*/, "", name)
      scope = ""
      if (match($0, /scope:[[:space:]]*[a-z-]+/)) {
        scope = substr($0, RSTART, RLENGTH); sub(/scope:[[:space:]]*/, "", scope)
      }
      profs = ""
      if (match($0, /profiles:[[:space:]]*\[[^]]*\]/)) {
        profs = substr($0, RSTART, RLENGTH)
        sub(/profiles:[[:space:]]*\[/, "", profs); sub(/\]/, "", profs); gsub(/[[:space:]]/, "", profs)
      }
      print name "|" scope "|" profs
    }
  ' "$meta")"

  manifest_names="$(printf '%s\n' "$manifest_rows" | awk -F'|' 'NF { print $1 }' | sort -u)"
  dir_names="$(find "$skills_dir" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort -u)"

  # 双向 bijection
  while read -r d; do [[ -n "$d" ]] && err "目录存在但 manifest 缺失: $d"; done \
    < <(comm -23 <(printf '%s\n' "$dir_names") <(printf '%s\n' "$manifest_names"))
  while read -r d; do [[ -n "$d" ]] && err "manifest 存在但目录缺失: $d"; done \
    < <(comm -13 <(printf '%s\n' "$dir_names") <(printf '%s\n' "$manifest_names"))

  # 逐行 scope / profile 校验
  used_profiles=""
  while IFS='|' read -r name scope profs; do
    [[ -z "$name" ]] && continue
    case "$valid_scopes" in
      *" $scope "*) : ;;
      *) err "scope 非法: $name -> '${scope:-<空>}'" ;;
    esac
    if [[ -n "$profs" ]]; then
      [[ "$scope" != "project" ]] && warn "$scope skill 不应携带 profiles: $name -> [$profs]"
      IFS=',' read -ra arr <<<"$profs"
      for pr in "${arr[@]}"; do
        used_profiles+="$pr"$'\n'
        printf '%s\n' "$defined_profiles" | grep -qx "$pr" \
          || err "引用未定义 profile: $name -> $pr"
      done
    fi
  done <<<"$manifest_rows"

  # 空 profile 警告
  while read -r pr; do
    [[ -z "$pr" ]] && continue
    printf '%s' "$used_profiles" | grep -qx "$pr" || warn "profile 无任何成员: $pr"
  done <<<"$defined_profiles"

  printf '  ok: %s skills / %s profiles\n' \
    "$(printf '%s\n' "$manifest_names" | grep -c .)" \
    "$(printf '%s\n' "$defined_profiles" | grep -c .)"
done

printf '\n== summary: %d error(s), %d warning(s) ==\n' "$errors" "$warnings"
[[ "$errors" -eq 0 ]]
