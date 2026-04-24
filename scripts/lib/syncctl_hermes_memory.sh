#!/bin/bash

set -euo pipefail

syncctl_hermes_memory_default_rules_relpath() {
  printf 'platforms/hermes/memory/redaction-rules.yaml'
}

syncctl_hermes_memory_default_rules_path() {
  printf '%s/%s' "$SYNCCTL_REPO_ROOT" "$(syncctl_hermes_memory_default_rules_relpath)"
}

syncctl_hermes_memory_reason_get() {
  local reason="$1"
  local key="$2"
  printf '%s' "$reason" | tr ';' '\n' | awk -F'=' -v k="$key" '$1==k{print substr($0, index($0, "=")+1); exit}'
}

syncctl_hermes_memory_collect_tasks() {
  local tasks_file="$1"
  local platform="$2"
  local direction="$3"
  local repo_root="$4"
  local local_root="$5"

  local whitelist="$repo_root/memory/whitelist.yaml"
  local rules_rel
  rules_rel="$(syncctl_hermes_memory_default_rules_relpath)"
  local rules_file="$SYNCCTL_REPO_ROOT/$rules_rel"
  local snapshots_root="$repo_root/memory/snapshots"
  local memories_root="$local_root/memories"

  if [ "$direction" != "local-to-repo" ]; then
    local skip_task
    skip_task="$(syncctl_next_task_id)"
    syncctl_add_task "$tasks_file" "$skip_task" "$platform" "$direction" "memory" "memory" "skip" "-" "-" "never" "" "hermes memory" "memory_sync_only_local_to_repo"
    return 0
  fi

  if [ ! -f "$whitelist" ]; then
    local skip_task
    skip_task="$(syncctl_next_task_id)"
    syncctl_add_task "$tasks_file" "$skip_task" "$platform" "$direction" "memory" "memory" "skip" "-" "-" "never" "" "hermes memory" "memory_whitelist_missing:$whitelist"
    return 0
  fi

  if [ ! -f "$rules_file" ]; then
    local skip_task
    skip_task="$(syncctl_next_task_id)"
    syncctl_add_task "$tasks_file" "$skip_task" "$platform" "$direction" "memory" "memory" "skip" "-" "-" "never" "" "hermes memory" "memory_rules_missing:$rules_file"
    return 0
  fi

  mkdir -p "$snapshots_root"

  local entries_tmp
  entries_tmp="$(mktemp)"
  python3 - "$whitelist" > "$entries_tmp" <<'PY'
import re
import sys
from pathlib import Path

whitelist_path = Path(sys.argv[1])

try:
    import yaml
except ModuleNotFoundError:
    print("__ERROR__\tmissing_pyyaml\t-\t-")
    raise SystemExit(0)

try:
    data = yaml.safe_load(whitelist_path.read_text(encoding="utf-8")) or {}
except Exception as exc:
    print(f"__ERROR__\tinvalid_yaml:{exc.__class__.__name__}\t-\t-")
    raise SystemExit(0)

entries = data.get("entries")
if not isinstance(entries, list):
    raise SystemExit(0)

for entry in entries:
    if not isinstance(entry, dict):
        continue

    enabled = entry.get("enabled", True)
    if enabled is False:
        continue

    entry_id = str(entry.get("id", "")).strip()
    source_file = str(entry.get("source_file", "")).strip()
    if not entry_id or not source_file:
        print("__ERROR__\tmissing_id_or_source_file\t-\t-")
        continue

    if "/" in source_file or source_file.startswith("."):
        print(f"__ERROR__\tinvalid_source_file:{source_file}\t-\t-")
        continue

    snapshot_file = str(entry.get("snapshot_file") or f"{entry_id}.md").strip()
    if not snapshot_file:
        snapshot_file = f"{entry_id}.md"

    # 防止目录穿越，只允许扁平文件名
    if "/" in snapshot_file or ".." in snapshot_file:
        print(f"__ERROR__\tinvalid_snapshot_file:{snapshot_file}\t-\t-")
        continue

    # 统一文件名字符，避免奇怪路径字符
    snapshot_file = re.sub(r"[^A-Za-z0-9._-]", "_", snapshot_file)

    redaction_level = str(entry.get("redaction_level") or "standard").strip().lower()
    if redaction_level not in {"standard", "strict"}:
        redaction_level = "standard"

    print(f"{entry_id}\t{source_file}\t{snapshot_file}\t{redaction_level}")
PY

  local entry_id source_file snapshot_file redaction_level
  while IFS=$'\t' read -r entry_id source_file snapshot_file redaction_level; do
    [ -n "$entry_id" ] || continue

    if [ "$entry_id" = "__ERROR__" ]; then
      local skip_task
      skip_task="$(syncctl_next_task_id)"
      syncctl_add_task "$tasks_file" "$skip_task" "$platform" "$direction" "memory" "memory" "skip" "-" "-" "never" "" "hermes memory" "memory_whitelist_error:$source_file"
      continue
    fi

    local src="$memories_root/$source_file"
    local dst="$snapshots_root/$snapshot_file"
    local source_hash="missing"
    if [ -f "$src" ]; then
      source_hash="$(shasum -a 256 "$src" | awk '{print $1}')"
    fi

    local reason="source_file=$source_file;source_hash=$source_hash;rules=$rules_rel"
    local task_id
    task_id="$(syncctl_next_task_id)"
    syncctl_add_task "$tasks_file" "$task_id" "$platform" "$direction" "memory" "$entry_id" "hermes_memory_entry" "$src" "$dst" "never" "$redaction_level" "hermes memory/$entry_id" "$reason"
  done < "$entries_tmp"

  rm -f "$entries_tmp"
}

syncctl_hermes_memory_redact() {
  local src="$1"
  local dst="$2"
  local snapshot_id="$3"
  local source_file="$4"
  local redaction_level="$5"
  local rules_file="$6"

  python3 - "$src" "$dst" "$snapshot_id" "$source_file" "$redaction_level" "$rules_file" <<'PY'
import re
import sys
from pathlib import Path

src, dst, snapshot_id, source_file, redaction_level, rules_file = sys.argv[1:]

try:
    import yaml
except ModuleNotFoundError:
    raise SystemExit("missing PyYAML (python3 -m pip install --user PyYAML)")

rules_data = yaml.safe_load(Path(rules_file).read_text(encoding="utf-8")) or {}
levels = rules_data.get("levels") or {}
default_level = str(rules_data.get("default_level") or "standard").strip().lower()


class RuleError(RuntimeError):
    pass


def resolve_level(name: str, stack=None):
    if stack is None:
        stack = []
    key = (name or default_level or "standard").strip().lower()
    if key in stack:
        raise RuleError(f"redaction inherit cycle: {' -> '.join(stack + [key])}")

    cfg = levels.get(key) or {}
    merged = {
        "regex_replace": [],
        "line_mask_keywords": [],
    }

    parent = cfg.get("inherit")
    if parent:
        base = resolve_level(str(parent), stack + [key])
        merged["regex_replace"].extend(base.get("regex_replace", []))
        merged["line_mask_keywords"].extend(base.get("line_mask_keywords", []))

    merged["regex_replace"].extend(cfg.get("regex_replace") or [])
    merged["line_mask_keywords"].extend(cfg.get("line_mask_keywords") or [])
    return merged


level_cfg = resolve_level(redaction_level)
regex_rules = []
for item in level_cfg.get("regex_replace", []):
    if not isinstance(item, dict):
        continue
    pattern = item.get("pattern")
    if not pattern:
        continue
    replacement = str(item.get("replacement", "<REDACTED>"))
    regex_rules.append((re.compile(str(pattern), flags=re.MULTILINE), replacement))

line_keywords = [str(x).lower() for x in (level_cfg.get("line_mask_keywords") or []) if str(x).strip()]

text = Path(src).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")

for pattern, replacement in regex_rules:
    text = pattern.sub(replacement, text)

if line_keywords:
    masked_lines = []
    for line in text.split("\n"):
        line_low = line.lower()
        if any(keyword in line_low for keyword in line_keywords):
            masked_lines.append("<REDACTED_LINE>")
        else:
            masked_lines.append(line)
    text = "\n".join(masked_lines)

parts = [p.strip() for p in text.split("§") if p.strip()]
if parts:
    body = "\n§\n".join(parts)
else:
    body = text.strip()

body = "\n".join(line.rstrip() for line in body.split("\n")).strip()

output = (
    f"# memory_snapshot: {snapshot_id}\n"
    f"# source_file: {source_file}\n"
    f"# redaction_level: {redaction_level}\n\n"
    f"{body}\n"
)

Path(dst).write_text(output, encoding="utf-8")
PY
}

syncctl_check_hermes_memory_task() {
  local platform="$1"
  local scope="$2"
  local target="$3"
  local src="$4"
  local dst="$5"
  local redaction_level="$6"
  local reason="$7"
  local ops_file="$8"

  if [ ! -f "$src" ]; then
    syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "$(basename "$dst")" "$src" "$dst" "0" "memory_source_missing"
    return 0
  fi

  local source_file rules_rel rules_file
  source_file="$(syncctl_hermes_memory_reason_get "$reason" "source_file")"
  rules_rel="$(syncctl_hermes_memory_reason_get "$reason" "rules")"
  [ -n "$rules_rel" ] || rules_rel="$(syncctl_hermes_memory_default_rules_relpath)"
  rules_file="$SYNCCTL_REPO_ROOT/$rules_rel"

  if [ ! -f "$rules_file" ]; then
    syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "$(basename "$dst")" "$src" "$dst" "0" "memory_rules_missing"
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  if ! syncctl_hermes_memory_redact "$src" "$tmp" "$target" "$source_file" "$redaction_level" "$rules_file"; then
    rm -f "$tmp"
    syncctl_add_op "$ops_file" "skip" "$platform" "$scope" "$target" "$(basename "$dst")" "$src" "$dst" "0" "memory_redaction_failed"
    return 0
  fi

  local rel_path="$dst"
  case "$dst" in
    "$SYNCCTL_REPO_ROOT"/*)
      rel_path="${dst#"$SYNCCTL_REPO_ROOT/"}"
      ;;
  esac

  if [ ! -f "$dst" ]; then
    syncctl_add_op "$ops_file" "add" "$platform" "$scope" "$target" "$rel_path" "$src" "$dst" "0" "memory_sync"
  elif ! cmp -s "$tmp" "$dst"; then
    syncctl_add_op "$ops_file" "update" "$platform" "$scope" "$target" "$rel_path" "$src" "$dst" "0" "memory_sync"
  fi

  rm -f "$tmp"
}

syncctl_apply_hermes_memory_task() {
  local target="$1"
  local src="$2"
  local dst="$3"
  local redaction_level="$4"
  local reason="$5"

  if [ ! -f "$src" ]; then
    echo "[syncctl][memory] skip $target: source_missing $src" >&2
    return 2
  fi

  local expected_hash
  expected_hash="$(syncctl_hermes_memory_reason_get "$reason" "source_hash")"
  if [ -n "$expected_hash" ] && [ "$expected_hash" != "missing" ]; then
    local current_hash
    current_hash="$(shasum -a 256 "$src" | awk '{print $1}')"
    if [ "$current_hash" != "$expected_hash" ]; then
      echo "[syncctl][memory] skip $target: source changed after check (expected=$expected_hash current=$current_hash)" >&2
      return 3
    fi
  fi

  local source_file rules_rel rules_file
  source_file="$(syncctl_hermes_memory_reason_get "$reason" "source_file")"
  rules_rel="$(syncctl_hermes_memory_reason_get "$reason" "rules")"
  [ -n "$rules_rel" ] || rules_rel="$(syncctl_hermes_memory_default_rules_relpath)"
  rules_file="$SYNCCTL_REPO_ROOT/$rules_rel"

  if [ ! -f "$rules_file" ]; then
    echo "[syncctl][memory] skip $target: rules_missing $rules_file" >&2
    return 4
  fi

  local tmp
  tmp="$(mktemp)"
  if ! syncctl_hermes_memory_redact "$src" "$tmp" "$target" "$source_file" "$redaction_level" "$rules_file"; then
    rm -f "$tmp"
    echo "[syncctl][memory] skip $target: redaction_failed" >&2
    return 4
  fi

  mkdir -p "$(dirname "$dst")"
  if [ ! -f "$dst" ] || ! cmp -s "$tmp" "$dst"; then
    cp "$tmp" "$dst"
  fi

  rm -f "$tmp"
  return 0
}
