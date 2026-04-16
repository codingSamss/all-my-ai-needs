#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
TEMPLATE_CONFIG="$REPO_ROOT/platforms/hermes/config.template.yaml"
TARGET_CONFIG="$HERMES_HOME_DIR/config.yaml"
MODE="dry-run"
AUTO_YES="false"

usage() {
  cat <<'USAGE'
用法:
  ./scripts/sync_to_hermes.sh --dry-run
  ./scripts/sync_to_hermes.sh --sync-config
  ./scripts/sync_to_hermes.sh --sync-config --yes
  ./scripts/sync_to_hermes.sh --hermes-home /path/to/.hermes --dry-run

说明:
  - 默认模式为 --dry-run，只预览受管配置片段的合并结果。
  - --sync-config 会把 `platforms/hermes/config.template.yaml` 合并到 `~/.hermes/config.yaml`。
  - 合并策略：占位符（如 <PLAYWRIGHT_EXT_TOKEN>）优先保留本机已有非占位值；
    若本机缺失且存在同名环境变量（例如 PLAYWRIGHT_EXT_TOKEN 或 PLAYWRIGHT_MCP_EXTENSION_TOKEN），则使用环境变量值。
  - 本脚本仅处理受管配置片段，不会覆盖 skills/cron 同步策略。
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      ;;
    --sync-config)
      MODE="apply"
      ;;
    --yes)
      AUTO_YES="true"
      ;;
    --hermes-home)
      shift
      [ $# -gt 0 ] || { echo "[错误] --hermes-home 缺少参数"; exit 1; }
      HERMES_HOME_DIR="$1"
      TARGET_CONFIG="$HERMES_HOME_DIR/config.yaml"
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

if [ ! -f "$TEMPLATE_CONFIG" ]; then
  echo "[错误] 未找到模板文件: $TEMPLATE_CONFIG"
  exit 1
fi

mkdir -p "$HERMES_HOME_DIR"

if [ "$MODE" = "apply" ] && [ "$AUTO_YES" != "true" ]; then
  printf "[确认] 将更新 %s，继续？[y/N] " "$TARGET_CONFIG"
  read -r answer || answer=""
  if [ "${answer:-}" != "y" ] && [ "${answer:-}" != "Y" ]; then
    echo "[取消] 未执行写入。"
    exit 0
  fi
fi

echo "=== Hermes 配置同步（受管片段）==="
echo "模板: $TEMPLATE_CONFIG"
echo "目标: $TARGET_CONFIG"
echo "模式: $MODE"

python3 - "$TEMPLATE_CONFIG" "$TARGET_CONFIG" "$MODE" <<'PY'
from __future__ import annotations

import copy
import datetime as dt
import os
import re
import sys
from pathlib import Path

import yaml


def load_yaml(path: Path):
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


PLACEHOLDER_RE = re.compile(r"^<([A-Z0-9_]+)>$")


def placeholder_name(value):
    if not isinstance(value, str):
        return None
    m = PLACEHOLDER_RE.match(value)
    return m.group(1) if m else None


def is_placeholder(value) -> bool:
    return placeholder_name(value) is not None


PLACEHOLDER_ENV_ALIASES = {
    "PLAYWRIGHT_EXT_TOKEN": "PLAYWRIGHT_MCP_EXTENSION_TOKEN",
}


def merge_value(template, current, path, unresolved):
    if isinstance(template, dict):
        base = copy.deepcopy(current) if isinstance(current, dict) else {}
        for key, tval in template.items():
            cval = base.get(key)
            base[key] = merge_value(tval, cval, path + [str(key)], unresolved)
        return base

    if isinstance(template, list):
        current_list = current if isinstance(current, list) else []
        merged = []
        for i, tval in enumerate(template):
            cval = current_list[i] if i < len(current_list) else None
            merged.append(merge_value(tval, cval, path + [f"[{i}]"], unresolved))
        return merged

    name = placeholder_name(template)
    if name:
        if current is not None and current != "" and not is_placeholder(current):
            return current
        env_val = os.getenv(name)
        if not env_val:
            alias = PLACEHOLDER_ENV_ALIASES.get(name)
            if alias:
                env_val = os.getenv(alias)
        if env_val:
            return env_val
        pretty_path = ".".join(path).replace(".[", "[")
        unresolved.append(pretty_path + f" -> {template}")
        return template

    return template


def walk_template_paths(template, prefix):
    paths = []
    if isinstance(template, dict):
        for k, v in template.items():
            p = prefix + [str(k)]
            paths.extend(walk_template_paths(v, p))
        return paths
    if isinstance(template, list):
        for i, v in enumerate(template):
            p = prefix + [f"[{i}]"]
            paths.extend(walk_template_paths(v, p))
        return paths
    return [prefix]


def get_value_by_path(data, path):
    cur = data
    for raw in path:
        if raw.startswith("[") and raw.endswith("]"):
            if not isinstance(cur, list):
                return None
            idx = int(raw[1:-1])
            if idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or raw not in cur:
                return None
            cur = cur[raw]
    return cur


def fmt_path(path):
    out = []
    for part in path:
        if part.startswith("["):
            if out:
                out[-1] = out[-1] + part
            else:
                out.append(part)
        else:
            out.append(part)
    return ".".join(out)


def sensitive(path_str: str) -> bool:
    low = path_str.lower()
    markers = ["token", "secret", "password", "api_key", "authorization", "bearer"]
    return any(m in low for m in markers)


template_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
mode = sys.argv[3]

if mode not in {"dry-run", "apply"}:
    raise SystemExit("invalid mode")

template = load_yaml(template_path)
current = load_yaml(target_path)
if not isinstance(template, dict):
    raise SystemExit(f"模板格式错误: {template_path}")
if not isinstance(current, dict):
    raise SystemExit(f"目标配置格式错误: {target_path}")

unresolved = []
merged = copy.deepcopy(current)
for top_key, top_val in template.items():
    cur_val = merged.get(top_key)
    merged[top_key] = merge_value(top_val, cur_val, [top_key], unresolved)

changed = []
for path in walk_template_paths(template, []):
    before = get_value_by_path(current, path)
    after = get_value_by_path(merged, path)
    if before != after:
        changed.append(fmt_path(path))

if changed:
    print(f"[预览] 受管键将变更 {len(changed)} 项:")
    for p in changed:
        tag = " (sensitive)" if sensitive(p) else ""
        print(f"  - {p}{tag}")
else:
    print("[预览] 受管键无变化。")

if unresolved:
    print("[提示] 存在未解析占位符（可保留，或通过环境变量/本机现值补齐）:")
    for item in unresolved:
        print(f"  - {item}")

if mode == "dry-run":
    print("[完成] dry-run 未写入文件。")
    raise SystemExit(0)

if target_path.exists():
    backup = target_path.with_name(target_path.name + ".bak-" + dt.datetime.now().strftime("%Y%m%d%H%M%S"))
    backup.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[备份] {backup}")

target_path.write_text(
    yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
    encoding="utf-8",
)
print(f"[写入] {target_path}")
print("[完成] 配置模板合并完成。建议执行: hermes mcp list && hermes mcp test playwright-ext")
PY
