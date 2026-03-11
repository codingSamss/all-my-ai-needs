#!/usr/bin/env python3
"""Normalize recall diagnosis inputs for request replay and requestId-only flows."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


VALID_ENVS = {"sit", "uat", "prod"}
VALID_TARGET_TYPES = {"doc", "faq"}
TRACE_TARGET_MAX_COUNT = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to a JSON input file.")
    parser.add_argument("--json", help="Inline JSON input.")
    parser.add_argument("--env", help="Override environment: sit|uat|prod.")
    parser.add_argument("--target-type", help="Override target type: doc|faq.")
    parser.add_argument(
        "--target-id",
        action="append",
        default=[],
        help="Append one target ID. Repeat for multiple values.",
    )
    parser.add_argument("--request-id", help="Override requestId.")
    parser.add_argument("--config", help="Optional JSON/YAML environment config.")
    return parser.parse_args()


def load_json_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.json:
        return ensure_dict(json.loads(args.json), "root")
    if args.input:
        return ensure_dict(json.loads(Path(args.input).read_text(encoding="utf-8")), "root")
    if not sys.stdin.isatty():
        return ensure_dict(json.load(sys.stdin), "root")
    return {}


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


def clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def merge_unique(*groups: Iterable[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            normalized = clean_str(item)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def normalize_target_type(raw: Dict[str, Any], args: argparse.Namespace) -> str:
    if args.target_type:
        target_type = args.target_type.strip().lower()
    else:
        target_type = clean_str(raw.get("targetType"))
        target_type = target_type.lower() if target_type else None
    if not target_type:
        if clean_str(raw.get("docId")) or raw.get("docIds"):
            target_type = "doc"
        elif clean_str(raw.get("faqId")) or raw.get("faqIds"):
            target_type = "faq"
    if target_type not in VALID_TARGET_TYPES:
        raise SystemExit("targetType must be doc or faq")
    return target_type


def normalize_target_ids(raw: Dict[str, Any], args: argparse.Namespace, target_type: str) -> List[str]:
    candidates: List[str] = []
    candidates.extend(args.target_id)
    generic_single = clean_str(raw.get("targetId"))
    if generic_single:
        candidates.append(generic_single)
    candidates.extend(ensure_list(raw.get("targetIds")))
    if target_type == "doc":
        candidates.extend(ensure_list(raw.get("docIds")))
        single = clean_str(raw.get("docId"))
        if single:
            candidates.append(single)
    if target_type == "faq":
        candidates.extend(ensure_list(raw.get("faqIds")))
        single = clean_str(raw.get("faqId"))
        if single:
            candidates.append(single)

    target_ids = merge_unique(candidates)
    if not target_ids:
        raise SystemExit("at least one targetId/docId/faqId is required")
    if len(target_ids) > TRACE_TARGET_MAX_COUNT:
        raise SystemExit(f"traceTargetIds supports at most {TRACE_TARGET_MAX_COUNT} values")
    return target_ids


def normalize_env(raw: Dict[str, Any], args: argparse.Namespace) -> str:
    env = clean_str(args.env) or clean_str(raw.get("env"))
    if not env:
        raise SystemExit("env is required and must be sit, uat, or prod")
    env = env.lower()
    if env not in VALID_ENVS:
        raise SystemExit("env must be sit, uat, or prod")
    return env


def generate_request_id(env: str) -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"diag-{env}-{timestamp}"


def normalize_headers(raw_headers: Any) -> Dict[str, str]:
    headers = ensure_dict(raw_headers, "request.headers")
    normalized: Dict[str, str] = {}
    for key, value in headers.items():
        cleaned = clean_str(value)
        if cleaned is not None:
            normalized[str(key)] = cleaned
    return normalized


def normalize_request_block(raw: Dict[str, Any], target_ids: List[str], env: str, args: argparse.Namespace) -> Dict[str, Any]:
    request = ensure_dict(raw.get("request"), "request")
    nested_headers = request.get("headers")
    nested_body = request.get("body")

    if not request:
        top_headers = raw.get("headers")
        top_body = raw.get("body") or raw.get("requestBody")
        if top_headers is not None or top_body is not None:
            request = {"headers": top_headers, "body": top_body}
            nested_headers = request.get("headers")
            nested_body = request.get("body")

    if not request:
        return {}

    headers = normalize_headers(nested_headers)
    body = ensure_dict(nested_body, "request.body")
    warnings: List[str] = []

    request_id = clean_str(args.request_id) or clean_str(raw.get("requestId")) or clean_str(body.get("requestId"))
    if not request_id:
        request_id = generate_request_id(env)
        warnings.append("requestId was missing; generated a diagnostic requestId")
    body["requestId"] = request_id

    trace_eligible = isinstance(body.get("conditionFilter"), dict)
    existing_trace_ids = ensure_list(body.get("traceTargetIds"))
    if trace_eligible:
        body["traceTargetIds"] = merge_unique(target_ids, existing_trace_ids)
    elif existing_trace_ids:
        warnings.append("request already contains traceTargetIds without conditionFilter; left unchanged")
    else:
        warnings.append("conditionFilter is absent; traceTargetIds injection is skipped")

    return {
        "headers": headers,
        "body": body,
        "warnings": warnings,
        "traceEligible": trace_eligible,
    }


def load_env_config(config_path: Optional[str], env: str) -> Optional[Dict[str, Any]]:
    if not config_path:
        return None
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise SystemExit("PyYAML is required to load YAML config files")
        data = yaml.safe_load(text)
    config = ensure_dict(data, "config")
    environments = ensure_dict(config.get("environments"), "config.environments")
    return ensure_dict(environments.get(env), f"config.environments.{env}")


def summarize_request_body(body: Dict[str, Any]) -> Dict[str, Any]:
    condition = ensure_dict(body.get("conditionFilter"), "conditionFilter")
    company_scope = ensure_dict(condition.get("companyScopeFilter"), "companyScopeFilter")
    team_scope = ensure_dict(condition.get("teamScopeFilter"), "teamScopeFilter")
    space_scope = ensure_dict(condition.get("spaceScopeFilter"), "spaceScopeFilter")
    return {
        "requestId": body.get("requestId"),
        "query": body.get("query"),
        "topk": body.get("topk"),
        "userName": body.get("userName"),
        "knowTypeList": body.get("knowTypeList"),
        "recallLangList": body.get("recallLangList"),
        "traceTargetIds": body.get("traceTargetIds"),
        "conditionFilter": {
            "threshold": condition.get("threshold"),
            "companyScopeRange": company_scope.get("range"),
            "teamScopeRange": team_scope.get("range"),
            "spaceScopeRange": space_scope.get("range"),
            "spaceSkillCount": len(ensure_list(space_scope.get("skillIdList"))),
        },
    }


def main() -> None:
    args = parse_args()
    raw = load_json_payload(args)
    env = normalize_env(raw, args)
    target_type = normalize_target_type(raw, args)
    target_ids = normalize_target_ids(raw, args, target_type)
    request_block = normalize_request_block(raw, target_ids, env, args)

    top_request_id = clean_str(args.request_id) or clean_str(raw.get("requestId"))
    mode = "request" if request_block else "request_id"
    if mode == "request":
        request_id = request_block["body"]["requestId"]
    else:
        request_id = top_request_id
        if not request_id:
            raise SystemExit("requestId is required when request.headers/body is absent")

    warnings = merge_unique(
        ensure_list(raw.get("warnings")),
        request_block.get("warnings", []),
    )

    output: Dict[str, Any] = {
        "env": env,
        "mode": mode,
        "targetType": target_type,
        "targetIds": target_ids,
        "requestId": request_id,
        "shouldUseTraceApiFirst": True,
        "shouldUseTargetIdInElkFirst": True,
        "shouldInjectTraceTargetIdsOnLiveRequest": bool(request_block),
        "warnings": warnings,
    }

    if request_block:
        output["request"] = {
            "headers": request_block["headers"],
            "body": request_block["body"],
        }
        output["requestSummary"] = summarize_request_body(request_block["body"])
        output["traceEligible"] = request_block["traceEligible"]

    config = load_env_config(args.config, env)
    if config is not None:
        output["envConfig"] = config

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
