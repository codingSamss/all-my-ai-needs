#!/usr/bin/env python3
"""Compact trace/recordInfo payloads before reading them into model context."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


VECTOR_KEYWORDS = (
    "vector",
    "embedding",
    "queryvec",
    "search_vec",
    "searchvec",
    "dense",
    "sparse",
)

IMPORTANT_REQUEST_KEYS = (
    "requestId",
    "query",
    "userName",
    "topk",
    "llmGenerateFlag",
    "traceTargetIds",
    "knowTypeList",
    "recallLangList",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to a JSON input file.")
    parser.add_argument("--json", help="Inline JSON input.")
    parser.add_argument(
        "--expand-step",
        action="append",
        default=[],
        help="Repeat to expand selected cmpId values.",
    )
    parser.add_argument("--max-list", type=int, default=8, help="Preview size for generic arrays.")
    parser.add_argument("--max-string", type=int, default=240, help="Max string length before truncation.")
    return parser.parse_args()


def ensure_dict(value: Any, field: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SystemExit(f"{field} must be a JSON object")
    return value


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.json:
        data = json.loads(args.json)
    elif args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    elif not sys.stdin.isatty():
        data = json.load(sys.stdin)
    else:
        raise SystemExit("provide --json, --input, or stdin")

    root = ensure_dict(data, "root")
    if isinstance(root.get("data"), dict):
        return ensure_dict(root["data"], "root.data")
    if isinstance(root.get("result"), dict):
        return ensure_dict(root["result"], "root.result")
    return root


def looks_like_vector_key(key: str) -> bool:
    lowered = key.lower()
    return any(keyword in lowered for keyword in VECTOR_KEYWORDS)


def looks_like_numeric_vector(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 8:
        return False
    return all(isinstance(item, (int, float)) for item in value[:8])


def truncate_text(text: str, max_string: int) -> str:
    if len(text) <= max_string:
        return text
    head = max_string // 2
    tail = max_string - head
    return f"{text[:head]}...<truncated {len(text) - max_string} chars>...{text[-tail:]}"


def maybe_parse_json_string(text: str) -> Optional[Any]:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped[0] not in "{[":
        return None
    try:
        return json.loads(stripped)
    except Exception:
        return None


def compact_value(value: Any, max_list: int, max_string: int, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        compacted: Dict[str, Any] = {}
        for key, item in value.items():
            if looks_like_vector_key(key) and (
                looks_like_numeric_vector(item) or isinstance(item, str)
            ):
                if isinstance(item, list):
                    compacted[key] = f"<omitted_vector len={len(item)}>"
                else:
                    compacted[key] = "<omitted_vector>"
                continue
            compacted[key] = compact_value(item, max_list, max_string, key)
        return compacted

    if isinstance(value, list):
        if looks_like_vector_key(parent_key) and looks_like_numeric_vector(value):
            return f"<omitted_vector len={len(value)}>"
        preview = [compact_value(item, max_list, max_string, parent_key) for item in value[:max_list]]
        if len(value) > max_list:
            return {
                "preview": preview,
                "omittedCount": len(value) - max_list,
            }
        return preview

    if isinstance(value, str):
        parsed = maybe_parse_json_string(value)
        if parsed is not None:
            return compact_value(parsed, max_list, max_string, parent_key)
        return truncate_text(value, max_string)

    return value


def summarize_condition_filter(condition_filter: Dict[str, Any]) -> Dict[str, Any]:
    company_scope = ensure_dict(condition_filter.get("companyScopeFilter"), "companyScopeFilter")
    team_scope = ensure_dict(condition_filter.get("teamScopeFilter"), "teamScopeFilter")
    space_scope = ensure_dict(condition_filter.get("spaceScopeFilter"), "spaceScopeFilter")
    return {
        "threshold": condition_filter.get("threshold"),
        "companyScopeRange": company_scope.get("range"),
        "companySourceSystemCount": len(ensure_list(company_scope.get("sourceSystemList"))),
        "teamScopeRange": team_scope.get("range"),
        "teamSkillCount": len(ensure_list(team_scope.get("skillIdList"))),
        "spaceScopeRange": space_scope.get("range"),
        "spaceSkillCount": len(ensure_list(space_scope.get("skillIdList"))),
    }


def summarize_request_body(body: Any) -> Dict[str, Any]:
    if isinstance(body, str):
        parsed = maybe_parse_json_string(body)
        if parsed is None:
            return {"raw": truncate_text(body, 320)}
        body = parsed

    body_dict = ensure_dict(body, "requestBody")
    summary = {
        "keys": sorted(body_dict.keys()),
    }
    for key in IMPORTANT_REQUEST_KEYS:
        if key in body_dict:
            summary[key] = body_dict[key]

    condition_filter = ensure_dict(body_dict.get("conditionFilter"), "conditionFilter")
    if condition_filter:
        summary["conditionFilter"] = summarize_condition_filter(condition_filter)
    return summary


def extract_log_hints(text: str) -> Dict[str, Any]:
    hints: Dict[str, Any] = {}
    patterns = {
        "hit": r"\bhit=(true|false)\b",
        "isError": r"\bisError=(true|false)\b",
        "returnedHitCount": r"\breturnedHitCount=(\d+)\b",
        "totalHitCount": r"\btotalHitCount=(\d+)\b",
        "tookMs": r"\btookMs=(\d+)\b",
        "cmpId": r"\bcmpId=([a-zA-Z0-9_]+)\b",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            hints[key] = value if value not in {"true", "false"} else value == "true"

    target_ids = re.search(r"\btargetIds=\[([^\]]*)\]", text)
    if target_ids:
        ids = [item.strip() for item in target_ids.group(1).split(",") if item.strip()]
        hints["targetIds"] = ids

    if "requestDsl=" in text:
        prefix, request_dsl = text.split("requestDsl=", 1)
        hints["message"] = truncate_text(prefix.strip(), 200)
        parsed = maybe_parse_json_string(request_dsl)
        hints["requestDsl"] = compact_value(parsed if parsed is not None else request_dsl, 6, 220)
        return hints

    hints["message"] = truncate_text(text, 320)
    return hints


def summarize_blob(blob: Any, max_list: int, max_string: int) -> Any:
    if blob is None:
        return None
    if isinstance(blob, str):
        parsed = maybe_parse_json_string(blob)
        if parsed is not None:
            return compact_value(parsed, max_list, max_string)
        return extract_log_hints(blob)
    return compact_value(blob, max_list, max_string)


def summarize_detail(detail: Dict[str, Any], expanded: bool, max_list: int, max_string: int) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "targetUrl": detail.get("targetUrl"),
        "timeSpent": detail.get("timeSpent"),
        "error": detail.get("error"),
    }
    if expanded:
        summary["requestBody"] = summarize_blob(detail.get("requestBody"), max_list, max_string)
        summary["responseBody"] = summarize_blob(detail.get("responseBody"), max_list, max_string)
    return summary


def summarize_step(step: Dict[str, Any], expanded_steps: Iterable[str], max_list: int, max_string: int) -> Dict[str, Any]:
    cmp_id = step.get("cmpId")
    expanded = cmp_id in set(expanded_steps)
    details = [ensure_dict(item, "detail") for item in ensure_list(step.get("detailList"))]
    summary: Dict[str, Any] = {
        "cmpId": cmp_id,
        "cmpName": step.get("cmpName"),
        "timeSpent": step.get("timeSpent"),
        "operateMsg": truncate_text(str(step.get("operateMsg") or ""), max_string),
        "detailCount": len(details),
        "detailTargets": [detail.get("targetUrl") for detail in details[:4] if detail.get("targetUrl")],
    }
    if expanded and details:
        summary["details"] = [
            summarize_detail(detail, True, max_list, max_string) for detail in details
        ]
    return summary


def main() -> None:
    args = parse_args()
    record = load_payload(args)
    request_summary = summarize_request_body(record.get("requestBody"))
    steps = [ensure_dict(item, "step") for item in ensure_list(record.get("stepList"))]

    compacted = {
        "linkId": record.get("linkId"),
        "createTime": record.get("createTime"),
        "timeSpent": record.get("timeSpent"),
        "userName": record.get("userName"),
        "appId": record.get("appId"),
        "question": record.get("question"),
        "requestSummary": request_summary,
        "stepCount": len(steps),
        "steps": [
            summarize_step(step, args.expand_step, args.max_list, args.max_string) for step in steps
        ],
    }

    json.dump(compacted, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
