#!/usr/bin/env python3
"""Aggregate local Codex/Claude JSONL sessions into evidence for manual diary writing."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MARK_START = "<!-- SESSION_SUMMARY_AUTO_START -->"
MARK_END = "<!-- SESSION_SUMMARY_AUTO_END -->"

DEFAULT_VAULT_ROOT = (
    "/Users/suqi3/Library/Mobile Documents/iCloud~md~obsidian/Documents/Sam's"
)
DEFAULT_DIARY_DIR = "01_日记"
DEFAULT_TEMPLATE_NAME = "_日记模板.md"
DEFAULT_SECTION_TITLE = "会话总结（自动）"
DEFAULT_SOURCES = ("codex", "claude")

DEFAULT_EXCLUDE_CWD = ["rag-flow", "rag-recall", "ragflow", "ragrecall"]
DEFAULT_EXCLUDE_PATH = [
    "rag-flow",
    "rag-recall",
    "ragflow",
    "ragrecall",
    "/subagents/",
]
DEFAULT_LIMITS = {
    "max_user_messages_per_session": 60,
    "max_commands_per_session": 80,
    "max_dirs_in_report": 12,
    "max_commands_in_report": 15,
    "claude_mtime_window_days": 2,
}

NOISE_PATTERNS = [
    re.compile(r"^#\s*AGENTS\.md instructions", re.IGNORECASE),
    re.compile(r"<INSTRUCTIONS>", re.IGNORECASE),
    re.compile(r"<permissions instructions>", re.IGNORECASE),
    re.compile(r"<environment_context>", re.IGNORECASE),
    re.compile(r"<local-command-caveat>", re.IGNORECASE),
    re.compile(r"<local-command-stdout>", re.IGNORECASE),
    re.compile(r"<command-name>", re.IGNORECASE),
    re.compile(r"<command-message>", re.IGNORECASE),
    re.compile(r"<turn_aborted>", re.IGNORECASE),
    re.compile(r"\bYou are Codex\b", re.IGNORECASE),
    re.compile(r"\bCollaboration Mode\b", re.IGNORECASE),
    re.compile(r"^This session is being continued from a previous conversation", re.IGNORECASE),
    re.compile(r"\btoken_count\b", re.IGNORECASE),
]

WEEKDAY_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@dataclass
class SessionRecord:
    source: str
    session_id: str
    file_path: Path
    cwd: str = ""
    first_ts: dt.datetime | None = None
    last_ts: dt.datetime | None = None
    user_texts: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


@dataclass
class GroupSummary:
    cwd: str
    sessions: list[SessionRecord] = field(default_factory=list)
    sources: Counter[str] = field(default_factory=Counter)
    intents: list[str] = field(default_factory=list)
    commands: Counter[str] = field(default_factory=Counter)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_config = script_dir.parent / "references" / "excludes.json"
    parser = argparse.ArgumentParser(
        description="聚合当天会话证据，默认仅输出供人工总结；可选写入自动区块"
    )
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="统计日期 YYYY-MM-DD")
    parser.add_argument("--vault-root", default=DEFAULT_VAULT_ROOT, help="Obsidian Vault 根目录")
    parser.add_argument("--diary-dir", default=DEFAULT_DIARY_DIR, help="日记目录名，默认 01_日记")
    parser.add_argument("--template-name", default=DEFAULT_TEMPLATE_NAME, help="日记模板文件名")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="数据源，逗号分隔：codex,claude",
    )
    parser.add_argument(
        "--exclude-config",
        default=str(default_config),
        help="排除与限制配置 JSON 路径",
    )
    parser.add_argument(
        "--section-title",
        default=DEFAULT_SECTION_TITLE,
        help="写入日记的区块标题",
    )
    parser.add_argument(
        "--output-mode",
        choices=("evidence", "write-auto"),
        default="evidence",
        help="输出模式：evidence=仅输出证据（默认），write-auto=写入自动总结区块",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="(已废弃) 等同于 --output-mode evidence，默认行为即 evidence 模式",
    )
    return parser.parse_args()


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def append_unique(items: list[str], value: str, limit: int) -> None:
    if not value:
        return
    if value in items:
        return
    if len(items) >= limit:
        return
    items.append(value)


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"[orbit-session-diary] 日期格式错误: {value}") from exc


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone()
    return parsed


def is_target_day(ts: dt.datetime | None, target_day: dt.date) -> bool:
    if ts is None:
        return False
    return ts.date() == target_day


def shorten_text(text: str, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def is_noise_text(text: str) -> bool:
    if not text:
        return True
    if len(text) < 4:
        return True
    for pattern in NOISE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_user_text(text: str) -> str:
    cleaned = shorten_text(text, limit=420)
    if is_noise_text(cleaned):
        return ""
    return cleaned


def sanitize_command(command: str) -> str:
    compact = re.sub(r"\s+", " ", command).strip()
    if not compact:
        return ""
    for shell_prefix in ("/bin/zsh -lc ", "zsh -lc ", "bash -lc "):
        if compact.startswith(shell_prefix):
            compact = compact[len(shell_prefix) :].strip().strip("'").strip('"')
            break
    if "<<" in compact:
        compact = compact.split("<<", 1)[0].strip()
    return shorten_text(compact, limit=300)


def safe_json_load(line: str) -> dict[str, Any] | None:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def extract_texts(node: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(node, str):
        texts.append(node)
        return texts
    if isinstance(node, list):
        for item in node:
            texts.extend(extract_texts(item))
        return texts
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "tool_result":
            return texts
        text_value = node.get("text")
        if isinstance(text_value, str):
            texts.append(text_value)
        if "content" in node:
            texts.extend(extract_texts(node.get("content")))
        return texts
    return texts


def should_exclude_value(value: str, keywords: list[str]) -> bool:
    if not value:
        return False
    lowered = value.lower()
    normalized = normalize_token(value)
    for keyword in keywords:
        kw = keyword.lower().strip()
        if not kw:
            continue
        if "/" in kw:
            if kw in lowered:
                return True
            continue
        normalized_kw = normalize_token(kw)
        if normalized_kw and normalized_kw in normalized:
            return True
    return False


def load_config(config_path: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"[orbit-session-diary] 配置读取失败: {config_path}: {exc}") from exc

    merged = dict(DEFAULT_LIMITS)
    merged.update({k: v for k, v in cfg.items() if k in DEFAULT_LIMITS})

    exclude_cwd = cfg.get("exclude_cwd_keywords", DEFAULT_EXCLUDE_CWD)
    exclude_path = cfg.get("exclude_path_keywords", DEFAULT_EXCLUDE_PATH)
    skip_subagents = bool(cfg.get("skip_subagents", True))

    return {
        "exclude_cwd_keywords": list(exclude_cwd),
        "exclude_path_keywords": list(exclude_path),
        "skip_subagents": skip_subagents,
        **merged,
    }


def parse_sources(raw_sources: str) -> set[str]:
    sources = {item.strip().lower() for item in raw_sources.split(",") if item.strip()}
    unsupported = sources - {"codex", "claude"}
    if unsupported:
        raise SystemExit(f"[orbit-session-diary] 不支持的数据源: {', '.join(sorted(unsupported))}")
    if not sources:
        raise SystemExit("[orbit-session-diary] --sources 不能为空")
    return sources


def mark_timestamp(record: SessionRecord, ts: dt.datetime) -> None:
    if record.first_ts is None or ts < record.first_ts:
        record.first_ts = ts
    if record.last_ts is None or ts > record.last_ts:
        record.last_ts = ts


def parse_call_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        arguments = arguments.strip()
        if not arguments:
            return {}
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def extract_commands_from_function_call(name: str, arguments: Any) -> list[str]:
    commands: list[str] = []
    args_obj = parse_call_arguments(arguments)
    lowered = name.lower()

    if lowered.endswith("exec_command"):
        cmd = args_obj.get("cmd")
        if isinstance(cmd, str):
            commands.append(cmd)
        return commands

    if lowered.endswith("parallel"):
        tool_uses = args_obj.get("tool_uses")
        if isinstance(tool_uses, list):
            for tool_use in tool_uses:
                if not isinstance(tool_use, dict):
                    continue
                recipient = str(tool_use.get("recipient_name", ""))
                if not recipient.lower().endswith("exec_command"):
                    continue
                parameters = tool_use.get("parameters")
                if isinstance(parameters, dict):
                    cmd = parameters.get("cmd")
                    if isinstance(cmd, str):
                        commands.append(cmd)
        return commands

    if lowered in {"apply_patch", "functions.apply_patch"}:
        commands.append("apply_patch")
        return commands

    return commands


def parse_codex_file(
    file_path: Path,
    target_day: dt.date,
    cfg: dict[str, Any],
) -> SessionRecord | None:
    if should_exclude_value(str(file_path), cfg["exclude_path_keywords"]):
        return None

    record = SessionRecord(source="codex", session_id=file_path.stem, file_path=file_path)
    saw_target_event = False
    max_user_msgs = int(cfg["max_user_messages_per_session"])
    max_commands = int(cfg["max_commands_per_session"])

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                striped = line.strip()
                if not striped:
                    continue
                if '"type":"session_meta"' in striped:
                    data = safe_json_load(striped)
                    if data:
                        payload = data.get("payload")
                        if isinstance(payload, dict):
                            session_id = payload.get("id")
                            cwd = payload.get("cwd")
                            if isinstance(session_id, str) and session_id:
                                record.session_id = session_id
                            if isinstance(cwd, str) and cwd:
                                record.cwd = cwd
                                if should_exclude_value(cwd, cfg["exclude_cwd_keywords"]):
                                    return None
                    continue

                if len(striped) > 500000:
                    continue

                data = safe_json_load(striped)
                if data is None:
                    continue

                ts = parse_timestamp(data.get("timestamp"))
                if not is_target_day(ts, target_day):
                    continue

                saw_target_event = True
                if ts:
                    mark_timestamp(record, ts)

                data_type = data.get("type")
                if data_type == "response_item":
                    payload = data.get("payload")
                    if not isinstance(payload, dict):
                        continue
                    payload_type = payload.get("type")

                    if payload_type == "message" and payload.get("role") == "user":
                        for text in extract_texts(payload.get("content")):
                            cleaned = sanitize_user_text(text)
                            append_unique(record.user_texts, cleaned, max_user_msgs)
                        continue

                    if payload_type == "function_call":
                        call_name = str(payload.get("name", ""))
                        for command in extract_commands_from_function_call(
                            call_name, payload.get("arguments")
                        ):
                            cleaned = sanitize_command(command)
                            append_unique(record.commands, cleaned, max_commands)
                        continue

                if data_type == "function_call":
                    call_name = str(data.get("name", ""))
                    for command in extract_commands_from_function_call(
                        call_name, data.get("arguments")
                    ):
                        cleaned = sanitize_command(command)
                        append_unique(record.commands, cleaned, max_commands)

    except OSError:
        return None

    if should_exclude_value(record.cwd, cfg["exclude_cwd_keywords"]):
        return None
    if not saw_target_event:
        return None
    if not record.cwd:
        record.cwd = "(unknown-cwd)"
    if not record.user_texts and not record.commands:
        return None
    return record


CLAUDE_READONLY_TOOLS = frozenset({
    "read", "glob", "grep", "webfetch", "websearch",
    "taskoutput", "tasklist", "taskget",
    "listmcpresourcestool", "readmcpresourcetool",
})


def extract_command_from_tool_use(tool_name: str, tool_input: Any) -> str:
    if tool_name.lower() in CLAUDE_READONLY_TOOLS:
        return ""
    if not isinstance(tool_input, dict):
        return tool_name
    if tool_name.lower() == "bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            return command
    for key in ("file_path", "path", "command", "pattern"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return f"{tool_name} {value}"
    return tool_name


def parse_claude_file(
    file_path: Path,
    target_day: dt.date,
    cfg: dict[str, Any],
) -> SessionRecord | None:
    if should_exclude_value(str(file_path), cfg["exclude_path_keywords"]):
        return None
    if cfg["skip_subagents"] and "/subagents/" in str(file_path):
        return None

    record = SessionRecord(source="claude", session_id=file_path.stem, file_path=file_path)
    saw_target_event = False
    max_user_msgs = int(cfg["max_user_messages_per_session"])
    max_commands = int(cfg["max_commands_per_session"])

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                striped = line.strip()
                if not striped:
                    continue
                if len(striped) > 500000:
                    continue

                data = safe_json_load(striped)
                if data is None:
                    continue

                ts = parse_timestamp(data.get("timestamp"))
                if not is_target_day(ts, target_day):
                    continue

                saw_target_event = True
                if ts:
                    mark_timestamp(record, ts)

                cwd = data.get("cwd")
                if isinstance(cwd, str) and cwd:
                    record.cwd = record.cwd or cwd
                    if should_exclude_value(cwd, cfg["exclude_cwd_keywords"]):
                        return None

                session_id = data.get("sessionId")
                if isinstance(session_id, str) and session_id:
                    record.session_id = session_id

                data_type = data.get("type")
                if data_type == "user":
                    message = data.get("message")
                    if isinstance(message, dict):
                        for text in extract_texts(message.get("content")):
                            cleaned = sanitize_user_text(text)
                            append_unique(record.user_texts, cleaned, max_user_msgs)
                    continue

                if data_type == "assistant":
                    message = data.get("message")
                    if not isinstance(message, dict):
                        continue
                    content = message.get("content")
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") != "tool_use":
                            continue
                        tool_name = str(item.get("name", ""))
                        command = extract_command_from_tool_use(tool_name, item.get("input"))
                        cleaned = sanitize_command(command)
                        append_unique(record.commands, cleaned, max_commands)

    except OSError:
        return None

    if should_exclude_value(record.cwd, cfg["exclude_cwd_keywords"]):
        return None
    if not saw_target_event:
        return None
    if not record.cwd:
        record.cwd = "(unknown-cwd)"
    if not record.user_texts and not record.commands:
        return None
    return record


def discover_codex_files(target_day: dt.date) -> list[Path]:
    root = Path(os.path.expanduser("~/.codex/sessions"))
    day_dir = root / f"{target_day.year:04d}" / f"{target_day.month:02d}" / f"{target_day.day:02d}"
    if not day_dir.exists():
        return []
    return sorted(day_dir.glob("*.jsonl"))


def discover_claude_files(target_day: dt.date, cfg: dict[str, Any]) -> list[Path]:
    root = Path(os.path.expanduser("~/.claude/projects"))
    if not root.exists():
        return []

    start = dt.datetime.combine(target_day, dt.time.min)
    end = start + dt.timedelta(days=1)
    window_days = int(cfg["claude_mtime_window_days"])
    min_mtime = (start - dt.timedelta(days=window_days)).timestamp()
    max_mtime = (end + dt.timedelta(days=window_days)).timestamp()

    files: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(".jsonl"):
                continue
            file_path = Path(dirpath) / filename
            if should_exclude_value(str(file_path), cfg["exclude_path_keywords"]):
                continue
            if cfg["skip_subagents"] and "/subagents/" in str(file_path):
                continue
            try:
                stat = file_path.stat()
            except OSError:
                continue
            if stat.st_mtime < min_mtime or stat.st_mtime > max_mtime:
                continue
            files.append(file_path)
    return sorted(files)


def infer_intent(record: SessionRecord) -> str:
    for text in record.user_texts:
        if text:
            return text
    if record.commands:
        return f"执行：{record.commands[0]}"
    return "无显式意图"


def build_group_summaries(
    records: list[SessionRecord],
) -> tuple[list[GroupSummary], Counter[str]]:
    grouped: dict[str, GroupSummary] = {}
    command_counter: Counter[str] = Counter()

    for record in records:
        cwd = record.cwd or "(unknown-cwd)"
        group = grouped.get(cwd)
        if group is None:
            group = GroupSummary(cwd=cwd)
            grouped[cwd] = group

        group.sessions.append(record)
        group.sources[record.source] += 1

        append_unique(group.intents, infer_intent(record), 4)

        for command in record.commands:
            if not command:
                continue
            group.commands[command] += 1
            command_counter[command] += 1

    groups = sorted(grouped.values(), key=lambda g: (-len(g.sessions), g.cwd))
    return groups, command_counter


def render_section(
    section_title: str,
    target_day: dt.date,
    records: list[SessionRecord],
    groups: list[GroupSummary],
    command_counter: Counter[str],
    sources: set[str],
    cfg: dict[str, Any],
) -> str:
    now_text = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exclude_preview = ", ".join(cfg["exclude_cwd_keywords"]) if cfg["exclude_cwd_keywords"] else "无"
    lines: list[str] = [
        f"## {section_title}",
        MARK_START,
        f"> 自动生成：{now_text}",
        f"> 统计日期：{target_day.isoformat()}",
        f"> 数据来源：{', '.join(sorted(sources))}",
        f"> 排除目录：{exclude_preview}",
        f"- 纳入会话：{len(records)}",
        f"- 涉及目录：{len(groups)}",
    ]

    if not records:
        lines.append("- 未发现符合条件的会话记录。")
        lines.append(MARK_END)
        return "\n".join(lines) + "\n"

    lines.append("### 写作校验（原始证据优先）")
    required_dirs = min(2, len(groups))
    lines.append(f"- 正文至少覆盖目录主线：{required_dirs} 个")
    lines.append("- 正文结论必须回看原始 jsonl，不以自动标签分类替代人工判断。")
    coverage_items: list[str] = []
    for group in groups[:3]:
        ratio = (len(group.sessions) / len(records)) * 100 if records else 0
        coverage_items.append(f"`{group.cwd}` {len(group.sessions)}会话（{ratio:.0f}%）")
    if coverage_items:
        lines.append(f"- 目录覆盖参考：{'；'.join(coverage_items)}")
    if len(groups) > 1 and (len(groups[0].sessions) / len(records) if records else 0) >= 0.7:
        lines.append("- 偏题提醒：单目录占比过高，正文必须补写其他目录的当日主线。")

    lines.append("### 分目录操作")
    max_dirs = int(cfg["max_dirs_in_report"])
    shown_groups = groups[:max_dirs]
    for group in shown_groups:
        lines.append(f"#### `{group.cwd}`")
        lines.append(
            f"- 会话数：{len(group.sessions)}（codex {group.sources.get('codex', 0)} / claude {group.sources.get('claude', 0)}）"
        )
        if group.intents:
            lines.append(f"- 主要诉求：{'；'.join(group.intents[:3])}")
        if group.commands:
            cmd_items: list[str] = []
            for command, count in group.commands.most_common(4):
                if count > 1:
                    cmd_items.append(f"`{command}`×{count}")
                else:
                    cmd_items.append(f"`{command}`")
            lines.append(f"- 关键操作：{'；'.join(cmd_items)}")

    if len(groups) > max_dirs:
        lines.append(f"- 其余目录：{len(groups) - max_dirs} 个（已省略）")

    max_commands = int(cfg["max_commands_in_report"])
    repeated = [(cmd, cnt) for cmd, cnt in command_counter.most_common(max_commands) if cnt > 1]
    if repeated:
        lines.append("### 高频命令")
        for command, count in repeated:
            lines.append(f"- `{command}` × {count}")
    else:
        lines.append(f"### 命令统计\n- 共 {sum(command_counter.values())} 条命令，无重复高频项")

    lines.append("### 原始会话索引（按时间倒序）")
    for index, record in enumerate(records, 1):
        first_ts = record.first_ts.isoformat(sep=" ", timespec="seconds") if record.first_ts else "unknown"
        last_ts = record.last_ts.isoformat(sep=" ", timespec="seconds") if record.last_ts else "unknown"
        lines.append(f"#### {index}. [{record.source}] `{record.session_id}`")
        lines.append(f"- 目录：`{record.cwd}`")
        lines.append(f"- 时间：{first_ts} -> {last_ts}")
        lines.append(f"- 日志：`{record.file_path}`")
        if record.user_texts:
            snippets = "；".join(f"`{shorten_text(text, limit=120)}`" for text in record.user_texts[:3])
            lines.append(f"- 用户原话（前3）：{snippets}")
        if record.commands:
            snippets = "；".join(f"`{shorten_text(command, limit=120)}`" for command in record.commands[:3])
            lines.append(f"- 命令索引（前3）：{snippets}")

    lines.append(MARK_END)
    return "\n".join(lines) + "\n"


def render_compact_section(
    section_title: str,
    target_day: dt.date,
    records: list[SessionRecord],
    groups: list[GroupSummary],
    sources: set[str],
) -> str:
    """写入日记的紧凑索引格式，只做证据摘要，不堆细节。"""
    now_text = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        f"## {section_title}",
        MARK_START,
        f"> 证据生成时间：{now_text}",
        f"> 统计日期：{target_day.isoformat()}",
        f"> 数据来源：{', '.join(sorted(sources))}",
        f"- 纳入会话：{len(records)}",
        f"- 涉及目录：{len(groups)}",
    ]

    if not records:
        lines.append("- 未发现符合条件的会话记录。")
        lines.append(MARK_END)
        return "\n".join(lines) + "\n"

    required_dirs = min(2, len(groups))
    dir_names = [Path(g.cwd).name or g.cwd for g in groups[:3]]
    lines.append(
        f"- 写作校验：正文至少覆盖 {required_dirs} 条目录主线"
        f"（本日目录覆盖为 {'、'.join(dir_names)}）"
    )
    lines.append("- 证据说明：本区块只做索引，正文请基于原始 jsonl 人工总结。")
    lines.append(MARK_END)
    return "\n".join(lines) + "\n"


def ensure_seed_diary(template_path: Path, target_day: dt.date) -> str:
    date_text = target_day.isoformat()
    weekday_text = WEEKDAY_ZH[target_day.weekday()]

    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        template = template.replace("{{date}}", date_text)
        template = template.replace("{{weekday}}", weekday_text)
        template = template.replace("{{today_plan_note}}", f"{date_text} 计划")
        template = re.sub(r"\{\{[^{}]+\}\}", "待补充", template)
        return template.rstrip() + "\n"

    return (
        f"---\n"
        f"date: {date_text}\n"
        f"weekday: {weekday_text}\n"
        f"tags: [daily]\n"
        f"---\n"
        f"\n"
        f"# {date_text} {weekday_text}\n"
        f"\n"
        f"## 今天做了什么\n"
        f"- [ ] 待补充\n"
        f"\n"
        f"## 主题聚合（核心）\n"
        f"- 待补充\n"
        f"\n"
        f"## 结果汇总\n"
        f"- 待补充\n"
        f"\n"
        f"## 关联项目\n"
        f"- 待补充\n"
    )


def upsert_section(document: str, section_title: str, new_section: str) -> str:
    marker_start = document.find(MARK_START)
    marker_end = document.find(MARK_END, marker_start + 1) if marker_start != -1 else -1
    section_heading = f"## {section_title}"

    if marker_start != -1 and marker_end != -1:
        block_start = document.rfind(section_heading, 0, marker_start)
        if block_start == -1:
            # 精确标题未命中，检查 marker 上方紧邻的行是否为任意 ## 标题
            pre = document[:marker_start].rstrip("\n")
            last_nl = pre.rfind("\n")
            candidate_line = pre[last_nl + 1 :]
            if candidate_line.startswith("## "):
                block_start = last_nl + 1 if last_nl >= 0 else 0
            else:
                block_start = marker_start
        block_end = marker_end + len(MARK_END)
        return (
            document[:block_start].rstrip()
            + "\n\n"
            + new_section.rstrip()
            + "\n\n"
            + document[block_end:].lstrip()
        )

    heading_pos = document.find(section_heading)
    if heading_pos != -1:
        next_heading = document.find("\n## ", heading_pos + len(section_heading))
        if next_heading == -1:
            next_heading = len(document)
        return (
            document[:heading_pos].rstrip()
            + "\n\n"
            + new_section.rstrip()
            + "\n\n"
            + document[next_heading:].lstrip()
        )

    for anchor in ("\n## 结果汇总", "\n## 关联项目"):
        pos = document.find(anchor)
        if pos != -1:
            return (
                document[:pos].rstrip()
                + "\n\n"
                + new_section.rstrip()
                + "\n\n"
                + document[pos:].lstrip()
            )

    return document.rstrip() + "\n\n" + new_section.rstrip() + "\n"


def collect_records(
    target_day: dt.date,
    sources: set[str],
    cfg: dict[str, Any],
) -> tuple[list[SessionRecord], dict[str, int]]:
    records: list[SessionRecord] = []
    stats = {
        "codex_candidates": 0,
        "claude_candidates": 0,
        "codex_included": 0,
        "claude_included": 0,
    }

    if "codex" in sources:
        codex_files = discover_codex_files(target_day)
        stats["codex_candidates"] = len(codex_files)
        for file_path in codex_files:
            parsed = parse_codex_file(file_path, target_day, cfg)
            if parsed is None:
                continue
            records.append(parsed)
            stats["codex_included"] += 1

    if "claude" in sources:
        claude_files = discover_claude_files(target_day, cfg)
        stats["claude_candidates"] = len(claude_files)
        for file_path in claude_files:
            parsed = parse_claude_file(file_path, target_day, cfg)
            if parsed is None:
                continue
            records.append(parsed)
            stats["claude_included"] += 1

    records.sort(key=lambda item: item.last_ts or item.first_ts or dt.datetime.min, reverse=True)
    return records, stats


def write_diary(
    vault_root: Path,
    diary_dir: str,
    template_name: str,
    target_day: dt.date,
    section_title: str,
    section_markdown: str,
    dry_run: bool,
) -> Path:
    diary_root = vault_root / diary_dir
    diary_month_dir = diary_root / f"{target_day.year:04d}-{target_day.month:02d}"
    diary_month_dir.mkdir(parents=True, exist_ok=True)
    diary_path = diary_month_dir / f"{target_day.isoformat()}.md"
    template_path = diary_root / template_name
    legacy_diary_path = diary_root / f"{target_day.isoformat()}.md"

    if diary_path.exists():
        original = diary_path.read_text(encoding="utf-8")
    elif legacy_diary_path.exists():
        # Backward compatibility: migrate old flat file layout into monthly folder.
        original = legacy_diary_path.read_text(encoding="utf-8")
    else:
        original = ensure_seed_diary(template_path, target_day)

    merged = upsert_section(original, section_title, section_markdown)
    if not merged.endswith("\n"):
        merged += "\n"

    if dry_run:
        return diary_path

    if merged != original:
        diary_path.write_text(merged, encoding="utf-8")
        os.utime(diary_path, None)
        if legacy_diary_path != diary_path and legacy_diary_path.exists():
            try:
                legacy_diary_path.unlink()
            except OSError:
                pass
    return diary_path


def main() -> None:
    args = parse_args()
    target_day = parse_date(args.date)
    sources = parse_sources(args.sources)
    cfg = load_config(Path(os.path.expanduser(args.exclude_config)))
    if args.dry_run:
        warnings.warn("--dry-run 已废弃，请改用 --output-mode evidence（当前默认行为）", DeprecationWarning, stacklevel=1)
    output_mode = "evidence" if args.dry_run else args.output_mode

    records, stats = collect_records(target_day, sources, cfg)
    groups, command_counter = build_group_summaries(records)

    # evidence 模式用完整渲染，write-auto 用紧凑索引
    evidence_markdown = render_section(
        section_title=args.section_title,
        target_day=target_day,
        records=records,
        groups=groups,
        command_counter=command_counter,
        sources=sources,
        cfg=cfg,
    )

    vault_root = Path(os.path.expanduser(args.vault_root))
    diary_path = (
        vault_root
        / args.diary_dir
        / f"{target_day.year:04d}-{target_day.month:02d}"
        / f"{target_day.isoformat()}.md"
    )
    if output_mode == "write-auto":
        compact_markdown = render_compact_section(
            section_title=args.section_title,
            target_day=target_day,
            records=records,
            groups=groups,
            sources=sources,
        )
        diary_path = write_diary(
            vault_root=vault_root,
            diary_dir=args.diary_dir,
            template_name=args.template_name,
            target_day=target_day,
            section_title=args.section_title,
            section_markdown=compact_markdown,
            dry_run=False,
        )

    print("[orbit-session-diary] 扫描完成")
    print(
        "[orbit-session-diary] 候选文件: "
        f"codex={stats['codex_candidates']} claude={stats['claude_candidates']}"
    )
    print(
        "[orbit-session-diary] 纳入会话: "
        f"codex={stats['codex_included']} claude={stats['claude_included']} total={len(records)}"
    )
    if output_mode == "evidence":
        print(f"[orbit-session-diary] 目标日记路径（待写入）: {diary_path}")
    else:
        print(f"[orbit-session-diary] 已写入: {diary_path}")
    print(f"[orbit-session-diary] 输出模式: {output_mode}")

    if output_mode == "evidence":
        weekday_label = WEEKDAY_ZH[target_day.weekday()]
        print(f"\n===== EVIDENCE PREVIEW (用于人工总结) =====")
        print(f"日期: {target_day.isoformat()} {weekday_label}\n")
        print(evidence_markdown)
    else:
        print("[orbit-session-diary] 已完成写入（含 touch 刷新时间戳）")


if __name__ == "__main__":
    main()
