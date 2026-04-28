#!/usr/bin/env python3
"""Normalize recall diagnosis inputs for request replay and requestId-only flows."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import re

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


VALID_ENVS = {"sit", "uat", "prod"}
VALID_TARGET_TYPES = {"doc", "faq"}
TRACE_TARGET_MAX_COUNT = 10
ROUTE_INDEX_COLUMNS = {2, 3, 4, 5}
XLSX_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
XLSX_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
TARGET_URL_INDEX_PATTERN = re.compile(r"targetUrl=GET /([^\s\[]+)")
TARGET_URL_CLUSTER_PATTERN = re.compile(r"\[cluster=([^\]]+)\]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to a JSON input file.")
    parser.add_argument("--json", help="Inline JSON input (prefer --input for large payloads).")
    parser.add_argument("--env", help="Override environment: sit|uat|prod.")
    parser.add_argument("--target-type", help="Override target type: doc|faq.")
    parser.add_argument(
        "--target-id",
        action="append",
        default=[],
        help="Append one target ID. Repeat for multiple values.",
    )
    parser.add_argument("--request-id", help="Override requestId.")
    parser.add_argument("--source-system", help="Override sourceSystem for ES console route resolution.")
    parser.add_argument("--request-dsl", help="Optional ELK requestDsl payload (JSON string or raw log text).")
    parser.add_argument("--config", help="Optional JSON/YAML environment config.")
    return parser.parse_args()


def load_json_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.json:
        try:
            return ensure_dict(json.loads(args.json), "root")
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"invalid --json payload at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
                "Prefer: write payload to file and use --input <file>."
            ) from exc
    if args.input:
        input_path = Path(args.input)
        try:
            return ensure_dict(json.loads(input_path.read_text(encoding="utf-8")), "root")
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"invalid JSON in --input file {input_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
    if not sys.stdin.isatty():
        try:
            return ensure_dict(json.load(sys.stdin), "root")
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"invalid JSON from stdin at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
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


def maybe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_source_system(raw: Dict[str, Any], args: argparse.Namespace, request_block: Dict[str, Any]) -> Optional[str]:
    body = maybe_dict(request_block.get("body"))
    top_body = maybe_dict(raw.get("body"))
    request_body = maybe_dict(raw.get("requestBody"))
    request_wrapper = maybe_dict(raw.get("request"))
    wrapper_body = maybe_dict(request_wrapper.get("body"))

    candidates = [
        args.source_system,
        raw.get("sourceSystem"),
        raw.get("source_system"),
        body.get("sourceSystem"),
        body.get("source_system"),
        top_body.get("sourceSystem"),
        top_body.get("source_system"),
        request_body.get("sourceSystem"),
        request_body.get("source_system"),
        wrapper_body.get("sourceSystem"),
        wrapper_body.get("source_system"),
    ]
    for value in candidates:
        normalized = clean_str(value)
        if normalized:
            return normalized
    return None


def normalize_request_dsl(raw: Dict[str, Any], args: argparse.Namespace, request_block: Dict[str, Any]) -> Optional[str]:
    body = maybe_dict(request_block.get("body"))
    top_body = maybe_dict(raw.get("body"))
    request_body = maybe_dict(raw.get("requestBody"))
    request_wrapper = maybe_dict(raw.get("request"))
    wrapper_body = maybe_dict(request_wrapper.get("body"))

    candidates = [
        args.request_dsl,
        raw.get("requestDsl"),
        raw.get("request_dsl"),
        raw.get("elkLog"),
        raw.get("elk_log"),
        body.get("requestDsl"),
        body.get("request_dsl"),
        top_body.get("requestDsl"),
        top_body.get("request_dsl"),
        request_body.get("requestDsl"),
        request_body.get("request_dsl"),
        wrapper_body.get("requestDsl"),
        wrapper_body.get("request_dsl"),
    ]
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        normalized = clean_str(value)
        if normalized:
            return normalized
    return None


def column_to_index(column: str) -> int:
    index = 0
    for ch in column:
        if "A" <= ch <= "Z":
            index = index * 26 + (ord(ch) - 64)
    return index


def parse_cell_value(cell: ET.Element, shared_strings: List[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("a:v", XLSX_NS)
    if cell_type == "s" and value_node is not None and value_node.text is not None:
        shared_index = int(value_node.text)
        if 0 <= shared_index < len(shared_strings):
            return shared_strings[shared_index]
        return ""
    if cell_type == "inlineStr":
        inline_node = cell.find("a:is/a:t", XLSX_NS)
        return inline_node.text if inline_node is not None and inline_node.text else ""
    if value_node is not None and value_node.text is not None:
        return value_node.text
    return ""


def load_shared_strings(xlsx_file: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in xlsx_file.namelist():
        return []
    sst = ET.fromstring(xlsx_file.read("xl/sharedStrings.xml"))
    shared_strings: List[str] = []
    for item in sst.findall("a:si", XLSX_NS):
        text = "".join((node.text or "") for node in item.findall(".//a:t", XLSX_NS))
        shared_strings.append(text)
    return shared_strings


def resolve_excel_path(config_path: str, excel_path_value: str) -> Path:
    config_file = Path(config_path)
    excel_path = Path(excel_path_value)
    if excel_path.is_absolute():
        return excel_path
    return (config_file.parent / excel_path).resolve()


def parse_route_rows_from_excel(xlsx_path: Path, sheet_name: Optional[str]) -> List[Dict[str, Any]]:
    if not xlsx_path.exists():
        raise SystemExit(f"source_system_cluster_map_excel file not found: {xlsx_path}")

    with zipfile.ZipFile(xlsx_path) as xlsx_file:
        workbook = ET.fromstring(xlsx_file.read("xl/workbook.xml"))
        rels = ET.fromstring(xlsx_file.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {
            rel.attrib["Id"]: "xl/" + rel.attrib["Target"] for rel in rels.findall("pr:Relationship", XLSX_NS)
        }
        sheets_root = workbook.find("a:sheets", XLSX_NS)
        if sheets_root is None:
            raise SystemExit(f"invalid xlsx workbook (missing sheets): {xlsx_path}")
        sheets = sheets_root.findall("a:sheet", XLSX_NS)
        if not sheets:
            raise SystemExit(f"invalid xlsx workbook (empty sheets): {xlsx_path}")

        selected_sheet = sheets[0]
        if sheet_name:
            selected_sheet = next((sheet for sheet in sheets if sheet.attrib.get("name") == sheet_name), None)  # type: ignore[assignment]
            if selected_sheet is None:
                raise SystemExit(f"sheet '{sheet_name}' not found in {xlsx_path}")

        relation_id = selected_sheet.attrib.get(XLSX_REL_ID) if selected_sheet is not None else None
        target = rid_to_target.get(relation_id or "")
        if not target:
            raise SystemExit(f"sheet target not found in workbook relations: {xlsx_path}")

        worksheet = ET.fromstring(xlsx_file.read(target))
        shared_strings = load_shared_strings(xlsx_file)

        rows: List[Dict[str, Any]] = []
        for row in worksheet.findall(".//a:sheetData/a:row", XLSX_NS):
            row_number = int(row.attrib.get("r", "0"))
            if row_number < 2:
                continue
            source_system = ""
            cluster_name = ""
            indices: List[str] = []
            for cell in row.findall("a:c", XLSX_NS):
                ref = cell.attrib.get("r", "")
                column = "".join(ch for ch in ref if ch.isalpha())
                column_index = column_to_index(column)
                value = clean_str(parse_cell_value(cell, shared_strings)) or ""
                if column_index == 1:
                    source_system = value
                elif column_index == 14:
                    cluster_name = value
                elif column_index in ROUTE_INDEX_COLUMNS and value:
                    indices.append(value)
            if source_system and cluster_name:
                rows.append(
                    {
                        "rowNumber": row_number,
                        "sourceSystem": source_system,
                        "cluster": cluster_name,
                        "indices": merge_unique(indices),
                    }
                )

        if not rows:
            raise SystemExit(f"no source_system -> cluster mapping found in {xlsx_path}")
        return rows


def parse_source_cluster_map_from_excel(xlsx_path: Path, sheet_name: Optional[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for row in parse_route_rows_from_excel(xlsx_path, sheet_name):
        source_system = clean_str(row.get("sourceSystem"))
        cluster_name = clean_str(row.get("cluster"))
        if source_system and cluster_name:
            mapping[source_system] = cluster_name
    return mapping


def parse_index_cluster_routes_from_excel(
    xlsx_path: Path, sheet_name: Optional[str]
) -> Dict[str, Dict[str, List[str]]]:
    index_routes: Dict[str, Dict[str, List[str]]] = {}
    for row in parse_route_rows_from_excel(xlsx_path, sheet_name):
        source_system = clean_str(row.get("sourceSystem"))
        cluster_name = clean_str(row.get("cluster"))
        for index_name in row.get("indices", []):
            normalized_index = clean_str(index_name)
            if not normalized_index or not cluster_name:
                continue
            entry = index_routes.setdefault(normalized_index, {"clusters": [], "sourceSystems": []})
            if cluster_name not in entry["clusters"]:
                entry["clusters"].append(cluster_name)
            if source_system and source_system not in entry["sourceSystems"]:
                entry["sourceSystems"].append(source_system)
    return index_routes


def load_source_system_cluster_map(
    es_console: Dict[str, Any], config_path: Optional[str]
) -> Dict[str, str]:
    inline_map = es_console.get("source_system_cluster_map")
    if isinstance(inline_map, dict) and inline_map:
        result: Dict[str, str] = {}
        for source_system, cluster in inline_map.items():
            source_key = clean_str(source_system)
            cluster_value = clean_str(cluster)
            if source_key and cluster_value:
                result[source_key] = cluster_value
        if result:
            return result

    excel_path_value = clean_str(es_console.get("source_system_cluster_map_excel"))
    if not excel_path_value:
        return {}
    if not config_path:
        raise SystemExit("config path is required when source_system_cluster_map_excel is configured")

    excel_path = resolve_excel_path(config_path, excel_path_value)
    sheet_name = clean_str(es_console.get("source_system_cluster_map_sheet"))
    return parse_source_cluster_map_from_excel(excel_path, sheet_name)


def load_index_cluster_routes(
    es_console: Dict[str, Any], config_path: Optional[str]
) -> Dict[str, Dict[str, List[str]]]:
    excel_path_value = clean_str(es_console.get("source_system_cluster_map_excel"))
    if not excel_path_value:
        return {}
    if not config_path:
        raise SystemExit("config path is required when source_system_cluster_map_excel is configured")

    excel_path = resolve_excel_path(config_path, excel_path_value)
    sheet_name = clean_str(es_console.get("source_system_cluster_map_sheet"))
    return parse_index_cluster_routes_from_excel(excel_path, sheet_name)


def flatten_index_candidates(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return merge_unique(part.strip() for part in value.split(","))
    if isinstance(value, list):
        flattened: List[str] = []
        for item in value:
            flattened.extend(flatten_index_candidates(item))
        return merge_unique(flattened)
    return []


def collect_index_fields(blob: Any) -> List[str]:
    if isinstance(blob, dict):
        collected: List[str] = []
        for key, value in blob.items():
            normalized_key = str(key).lower()
            if normalized_key in {"index", "indices", "_index"}:
                collected.extend(flatten_index_candidates(value))
            collected.extend(collect_index_fields(value))
        return merge_unique(collected)
    if isinstance(blob, list):
        collected: List[str] = []
        for item in blob:
            collected.extend(collect_index_fields(item))
        return merge_unique(collected)
    return []


def maybe_parse_json_blob(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None


def extract_index_names_from_request_dsl(
    request_dsl: Optional[str], known_indices: Iterable[str]
) -> List[str]:
    if not request_dsl:
        return []

    matched_indices: List[str] = []
    parsed = maybe_parse_json_blob(request_dsl)
    if parsed is not None:
        matched_indices.extend(collect_index_fields(parsed))

    for match in TARGET_URL_INDEX_PATTERN.findall(request_dsl):
        matched_indices.extend(flatten_index_candidates(match))

    for index_name in sorted(set(known_indices), key=len, reverse=True):
        if index_name and index_name in request_dsl:
            matched_indices.append(index_name)

    return merge_unique(index_name for index_name in matched_indices if index_name in set(known_indices))


def resolve_cluster_route_key(cluster_routes: Dict[str, Any], cluster_token: Optional[str]) -> Optional[str]:
    normalized_token = clean_str(cluster_token)
    if not normalized_token:
        return None
    if normalized_token in cluster_routes:
        return normalized_token

    cluster_key = f"集群{normalized_token}"
    if cluster_key in cluster_routes:
        return cluster_key

    for route_key, route_value in cluster_routes.items():
        route = maybe_dict(route_value)
        if clean_str(route.get("cluster_alias")) == normalized_token:
            return route_key
        if clean_str(route.get("cluster_id")) == normalized_token:
            return route_key
        if clean_str(route.get("trace_cluster_id")) == normalized_token:
            return route_key
    return None


def resolve_es_console_route(
    env_config: Dict[str, Any], source_system: Optional[str], request_dsl: Optional[str], config_path: Optional[str]
) -> Optional[Dict[str, Any]]:
    es_console = ensure_dict(env_config.get("es_console"), "envConfig.es_console")
    cluster_routes = ensure_dict(es_console.get("cluster_routes"), "envConfig.es_console.cluster_routes")
    if not cluster_routes:
        return None

    source_cluster_map = load_source_system_cluster_map(es_console, config_path)
    if not source_cluster_map:
        raise SystemExit("es_console.cluster_routes is configured but source_system_cluster_map is empty")

    cluster_name: Optional[str] = None
    resolved_by: Optional[str] = None
    matched_indices: List[str] = []
    matched_cluster_token: Optional[str] = None

    if request_dsl:
        cluster_match = TARGET_URL_CLUSTER_PATTERN.search(request_dsl)
        if cluster_match:
            matched_cluster_token = clean_str(cluster_match.group(1))
            route_key = resolve_cluster_route_key(cluster_routes, matched_cluster_token)
            if route_key:
                cluster_name = route_key
                resolved_by = "targetUrl.cluster"

    index_routes = load_index_cluster_routes(es_console, config_path)
    if cluster_name is None and request_dsl and index_routes:
        matched_indices = extract_index_names_from_request_dsl(request_dsl, index_routes.keys())
        if matched_indices:
            candidate_clusters: Optional[set[str]] = None
            for index_name in matched_indices:
                clusters = set(index_routes.get(index_name, {}).get("clusters", []))
                candidate_clusters = clusters if candidate_clusters is None else candidate_clusters & clusters
            if candidate_clusters and len(candidate_clusters) == 1:
                cluster_name = next(iter(candidate_clusters))
                resolved_by = "requestDsl.index"
            elif candidate_clusters and len(candidate_clusters) > 1 and source_system:
                source_cluster = clean_str(source_cluster_map.get(source_system))
                if source_cluster and source_cluster in candidate_clusters:
                    cluster_name = source_cluster
                    resolved_by = "requestDsl.index+sourceSystem"
            elif candidate_clusters is not None and len(candidate_clusters) == 0:
                raise SystemExit(
                    f"requestDsl matched indices from multiple clusters with no common route: {matched_indices}"
                )
            if cluster_name is None and matched_indices:
                ambiguous_clusters = sorted(
                    {
                        cluster
                        for index_name in matched_indices
                        for cluster in index_routes.get(index_name, {}).get("clusters", [])
                    }
                )
                raise SystemExit(
                    "requestDsl index route is ambiguous; matched indices="
                    f"{matched_indices}, candidate clusters={ambiguous_clusters}. "
                    "Please provide sourceSystem or verify ELK requestDsl."
                )

    if cluster_name is None and source_system:
        cluster_name = clean_str(source_cluster_map.get(source_system))
        if not cluster_name:
            raise SystemExit(
                f"sourceSystem '{source_system}' has no ES cluster mapping; "
                "please update 来源系统索引.xlsx or source_system_cluster_map"
            )
        resolved_by = "sourceSystem"

    if cluster_name is None:
        raise SystemExit(
            "unable to resolve ES console route: missing sourceSystem and requestDsl did not provide a unique known index"
        )

    route = ensure_dict(cluster_routes.get(cluster_name), f"envConfig.es_console.cluster_routes.{cluster_name}")
    page_url = clean_str(route.get("page_url"))
    if not page_url:
        raise SystemExit(f"envConfig.es_console.cluster_routes.{cluster_name}.page_url is required")

    resolved_route: Dict[str, Any] = {"cluster": cluster_name, "page_url": page_url}
    for key in ("cluster_alias", "instance_id", "region_id", "zone", "request_proxy_url"):
        value = clean_str(route.get(key))
        if value:
            resolved_route[key] = value
    if resolved_by:
        resolved_route["resolved_by"] = resolved_by
    if matched_indices:
        resolved_route["matched_indices"] = matched_indices
    if matched_cluster_token:
        resolved_route["matched_cluster_token"] = matched_cluster_token

    common_proxy = clean_str(es_console.get("request_proxy_url"))
    if common_proxy and "request_proxy_url" not in resolved_route:
        resolved_route["request_proxy_url"] = common_proxy

    return resolved_route


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


def find_header_value(headers: Dict[str, str], *names: str) -> Optional[str]:
    lowered = {str(key).lower(): value for key, value in headers.items()}
    for name in names:
        value = lowered.get(str(name).lower())
        if value is not None:
            return value
    return None


def backfill_replay_headers(headers: Dict[str, str], body: Dict[str, Any], warnings: List[str]) -> None:
    if not find_header_value(headers, "appId"):
        app_id = clean_str(body.get("appId"))
        if app_id:
            headers["appId"] = app_id
            warnings.append("headers.appId was missing; derived from request.body.appId")

    if not find_header_value(headers, "appChannel"):
        app_channel = clean_str(body.get("appChannel"))
        if app_channel:
            headers["appChannel"] = app_channel
            warnings.append("headers.appChannel was missing; derived from request.body.appChannel")


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
    backfill_replay_headers(headers, body, warnings)

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
            fallback_json = path.with_suffix(".json")
            if fallback_json.exists():
                data = json.loads(fallback_json.read_text(encoding="utf-8"))
            else:
                raise SystemExit("PyYAML is required to load YAML config files")
        else:
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
        "appId": body.get("appId"),
        "appChannel": body.get("appChannel"),
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
    source_system = normalize_source_system(raw, args, request_block)
    request_dsl = normalize_request_dsl(raw, args, request_block)

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
        "sourceSystem": source_system,
        "requestDslProvided": bool(request_dsl),
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
        es_route = resolve_es_console_route(config, source_system, request_dsl, args.config)
        if es_route:
            output["esConsoleRoute"] = es_route

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
