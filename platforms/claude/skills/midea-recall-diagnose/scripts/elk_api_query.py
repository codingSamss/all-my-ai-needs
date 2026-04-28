#!/usr/bin/env python3
"""Query ELK TRACE_TARGET_ES logs via Kibana APIs with browser session reuse."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit

try:
    import browser_cookie3  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"browser_cookie3 is required: {exc}")

try:
    import requests  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"requests is required: {exc}")

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

from elk_guard import build_kql, validate_kql


VALID_ENVS = ("sit", "uat", "prod")
VALID_MODES = ("first", "cmp", "hit_false")
VALID_BROWSERS = ("chrome", "chromium", "edge", "firefox", "brave")
VALID_ENDPOINTS = ("auto", "console_proxy", "internal_search")

PHASE_PATTERN = re.compile(r"\bphase=([^\s]+)")
CMP_PATTERN = re.compile(r"\bcmpId=([^\s]+)")
HIT_PATTERN = re.compile(r"\bhit=([^\s]+)")
TARGET_URL_PATTERN = re.compile(r"\btargetUrl=(.+?)(?:\s(?:hit=|targetIds=|isError=|requestDsl=)|$)")
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


class CliError(Exception):
    """Raised for user-input validation errors."""


class QueryError(Exception):
    """Raised when API querying fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, choices=VALID_ENVS)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--mode", default="first", choices=VALID_MODES)
    parser.add_argument("--cmp-id", default=None)
    parser.add_argument("--config", default=None, help="Path to env-config.local.yaml/json")
    parser.add_argument("--time-window", default="now-15m~now", help="Format: <gte>~<lte>")
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--sort-order", choices=("asc", "desc"), default="asc")
    parser.add_argument("--index-pattern", default=None)
    parser.add_argument("--browser", choices=VALID_BROWSERS, default=None)
    parser.add_argument("--api-endpoint", choices=VALID_ENDPOINTS, default="auto")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def ensure_dict(value: Any, field: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CliError(f"{field} must be an object")
    return value


def parse_time_window(spec: str) -> Tuple[str, str]:
    if "~" not in spec:
        raise CliError("--time-window must be '<gte>~<lte>'")
    gte, lte = [part.strip() for part in spec.split("~", 1)]
    if not gte or not lte:
        raise CliError("--time-window must include both gte and lte")
    return gte, lte


def normalize_index_pattern(pattern: Optional[str]) -> str:
    value = clean_str(pattern) or "logstash*"
    if "*" in value or "," in value:
        return value
    return f"{value}*"


def resolve_default_config() -> Path:
    base = Path(__file__).resolve().parent.parent / "references"
    if yaml is None:
        candidates = [
            base / "env-config.local.json",
            base / "env-config.local.yaml",
            base / "env-config.example.yaml",
        ]
    else:
        candidates = [
            base / "env-config.local.yaml",
            base / "env-config.local.json",
            base / "env-config.example.yaml",
        ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise CliError("No env config found under references/")


def load_config(path_arg: Optional[str], env: str) -> Tuple[Dict[str, Any], Path]:
    config_path = Path(path_arg) if path_arg else resolve_default_config()
    if not config_path.exists():
        raise CliError(f"Config not found: {config_path}")

    suffix = config_path.suffix.lower()
    if suffix == ".json":
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        if yaml is None:
            fallback_json = config_path.with_suffix(".json")
            if fallback_json.exists():
                config_path = fallback_json
                config = json.loads(config_path.read_text(encoding="utf-8"))
            else:
                raise CliError("PyYAML is required to read YAML config")
        else:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    root = ensure_dict(config, "config")
    envs = ensure_dict(root.get("environments"), "config.environments")
    env_cfg = ensure_dict(envs.get(env), f"config.environments.{env}")
    return env_cfg, config_path


def derive_api_base_url(elk_cfg: Dict[str, Any]) -> str:
    explicit = clean_str(elk_cfg.get("api_base_url"))
    if explicit:
        return explicit.rstrip("/")

    discover = clean_str(elk_cfg.get("discover_base_url"))
    if not discover:
        raise CliError("Missing elk.api_base_url and elk.discover_base_url")

    parsed = urlsplit(discover)
    if not parsed.scheme or not parsed.netloc:
        raise CliError(f"Invalid discover_base_url: {discover}")
    return f"{parsed.scheme}://{parsed.netloc}"


def endpoint_key_to_path(key: str) -> str:
    mapping = {
        "console_proxy": "/api/console/proxy",
        "internal_search": "/internal/search/es",
    }
    if key not in mapping:
        raise CliError(f"Unknown API endpoint key: {key}")
    return mapping[key]


def normalize_endpoint_path(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise CliError("Empty endpoint in elk.api_endpoint_order")
    if not value.startswith("/"):
        value = f"/{value}"
    return value


def resolve_endpoint_order(elk_cfg: Dict[str, Any], arg_choice: str) -> List[str]:
    if arg_choice != "auto":
        return [endpoint_key_to_path(arg_choice)]

    configured = elk_cfg.get("api_endpoint_order")
    paths: List[str] = []
    if isinstance(configured, list):
        for item in configured:
            raw = clean_str(item)
            if not raw:
                continue
            if raw in ("console_proxy", "internal_search"):
                paths.append(endpoint_key_to_path(raw))
            else:
                paths.append(normalize_endpoint_path(raw))
    if paths:
        return paths

    return ["/api/console/proxy", "/internal/search/es"]


def build_es_query(
    request_id: str,
    target_id: str,
    mode: str,
    cmp_id: Optional[str],
    gte: str,
    lte: str,
    size: int,
    sort_order: str,
) -> Dict[str, Any]:
    must: List[Dict[str, Dict[str, str]]] = [
        {"match_phrase": {"message": request_id}},
        {"match_phrase": {"message": target_id}},
        {"match_phrase": {"message": "TRACE_TARGET_ES"}},
    ]
    if mode == "cmp":
        if not cmp_id:
            raise CliError("mode=cmp requires --cmp-id")
        must.append({"match_phrase": {"message": cmp_id}})
    if mode == "hit_false":
        must.append({"match_phrase": {"message": "hit=false"}})

    return {
        "size": size,
        "sort": [{"@timestamp": {"order": sort_order}}],
        "query": {
            "bool": {
                "must": must,
                "filter": [{"range": {"@timestamp": {"gte": gte, "lte": lte}}}],
            }
        },
    }


def load_browser_cookies(hostname: str, browser: str):
    loader = {
        "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
        "brave": browser_cookie3.brave,
    }.get(browser)
    if loader is None:
        raise CliError(f"Unsupported browser: {browser}")
    return loader(domain_name=hostname)


def resolve_browser_name(cli_browser: Optional[str], elk_cfg: Dict[str, Any]) -> str:
    browser = clean_str(cli_browser) or clean_str(elk_cfg.get("cookie_browser")) or "chrome"
    if browser not in VALID_BROWSERS:
        raise CliError(f"Unsupported browser: {browser}")
    return browser


def build_session(api_base_url: str, browser: str, *, trust_env: bool) -> Tuple[requests.Session, str, int]:
    parsed = urlsplit(api_base_url)
    hostname = clean_str(parsed.hostname)
    if not hostname:
        raise CliError(f"Invalid api_base_url: {api_base_url}")

    jar = load_browser_cookies(hostname, browser)
    cookie_count = sum(1 for _ in jar)
    session = requests.Session()
    session.trust_env = trust_env
    session.cookies = jar
    return session, hostname, cookie_count


def extract_field(pattern: re.Pattern[str], message: str) -> Optional[str]:
    match = pattern.search(message)
    if not match:
        return None
    return clean_str(match.group(1))


def extract_event(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = ensure_dict(hit.get("_source"), "hit._source")
    message = str(source.get("message", ""))
    hit_flag_raw = extract_field(HIT_PATTERN, message)
    if hit_flag_raw == "true":
        hit_flag: Optional[bool] = True
    elif hit_flag_raw == "false":
        hit_flag = False
    else:
        hit_flag = None

    return {
        "timestamp": source.get("@timestamp"),
        "index": hit.get("_index"),
        "docId": hit.get("_id"),
        "cmpId": extract_field(CMP_PATTERN, message),
        "phase": extract_field(PHASE_PATTERN, message),
        "hit": hit_flag,
        "targetUrl": extract_field(TARGET_URL_PATTERN, message),
        "message": message,
    }


def extract_hits_from_response(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if endpoint == "/api/console/proxy":
        raw = payload
    elif endpoint == "/internal/search/es":
        raw = ensure_dict(payload.get("rawResponse"), "rawResponse")
    else:
        raise QueryError(f"Unsupported endpoint parser: {endpoint}")

    hits_obj = ensure_dict(raw.get("hits"), "hits")
    raw_total = hits_obj.get("total")
    if isinstance(raw_total, dict):
        total = raw_total.get("value")
    else:
        total = raw_total

    raw_hits = hits_obj.get("hits")
    if not isinstance(raw_hits, list):
        raise QueryError("hits.hits is missing or invalid")

    events = [extract_event(hit) for hit in raw_hits if isinstance(hit, dict)]

    return {
        "tookMs": raw.get("took"),
        "timedOut": raw.get("timed_out"),
        "total": total,
        "returned": len(events),
        "events": events,
    }


def post_json(
    session: requests.Session,
    url: str,
    *,
    params: Optional[Dict[str, str]],
    payload: Dict[str, Any],
    timeout: float,
) -> requests.Response:
    headers = {
        "content-type": "application/json",
        "kbn-xsrf": "true",
    }
    return session.post(url, params=params, headers=headers, json=payload, timeout=timeout)


def query_endpoint(
    session: requests.Session,
    api_base_url: str,
    endpoint: str,
    index_pattern: str,
    es_query: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:
    url = f"{api_base_url}{endpoint}"

    if endpoint == "/api/console/proxy":
        params = {
            "path": f"/{index_pattern}/_search",
            "method": "POST",
        }
        body = es_query
    elif endpoint == "/internal/search/es":
        params = None
        body = {
            "params": {
                "index": index_pattern,
                "body": es_query,
            },
            "strategy": "es",
        }
    else:
        raise QueryError(f"Unsupported endpoint: {endpoint}")

    response = post_json(session, url, params=params, payload=body, timeout=timeout)
    raw_text = response.text[:500]
    if response.status_code >= 400:
        raise QueryError(
            f"HTTP {response.status_code} from {endpoint}: {raw_text}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise QueryError(f"Non-JSON response from {endpoint}: {raw_text}") from exc

    hits = extract_hits_from_response(endpoint, payload)
    return {
        "endpoint": endpoint,
        "httpStatus": response.status_code,
        "result": hits,
    }


def run_query_once(
    *,
    session: requests.Session,
    api_base_url: str,
    endpoint_order: List[str],
    index_pattern: str,
    es_query: Dict[str, Any],
    timeout: float,
    network_mode: str,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    attempts: List[Dict[str, Any]] = []
    success: Optional[Dict[str, Any]] = None
    for endpoint in endpoint_order:
        try:
            outcome = query_endpoint(
                session=session,
                api_base_url=api_base_url,
                endpoint=endpoint,
                index_pattern=index_pattern,
                es_query=es_query,
                timeout=timeout,
            )
            attempts.append(
                {
                    "networkMode": network_mode,
                    "endpoint": endpoint,
                    "ok": True,
                    "httpStatus": outcome["httpStatus"],
                    "error": None,
                }
            )
            success = outcome
            break
        except (requests.RequestException, QueryError) as exc:
            attempts.append(
                {
                    "networkMode": network_mode,
                    "endpoint": endpoint,
                    "ok": False,
                    "httpStatus": None,
                    "error": str(exc),
                }
            )
    return attempts, success


def main() -> int:
    args = parse_args()

    if args.mode == "cmp" and not clean_str(args.cmp_id):
        print("FAIL: mode=cmp requires --cmp-id", file=sys.stderr)
        return 2

    try:
        gte, lte = parse_time_window(args.time_window)
        env_cfg, config_path = load_config(args.config, args.env)
        elk_cfg = ensure_dict(env_cfg.get("elk"), f"environments.{args.env}.elk")
        api_base_url = derive_api_base_url(elk_cfg)
        endpoint_order = resolve_endpoint_order(elk_cfg, args.api_endpoint)
        index_pattern = normalize_index_pattern(args.index_pattern or clean_str(elk_cfg.get("index_pattern")))

        kql = build_kql(args.request_id, args.target_id, args.mode, args.cmp_id)
        kql_ok, kql_errors = validate_kql(kql, args.request_id, args.target_id, args.mode, args.cmp_id)
        if not kql_ok:
            raise CliError(f"elk_guard self-check failed: {kql_errors}")

        es_query = build_es_query(
            request_id=args.request_id,
            target_id=args.target_id,
            mode=args.mode,
            cmp_id=args.cmp_id,
            gte=gte,
            lte=lte,
            size=args.size,
            sort_order=args.sort_order,
        )

        browser = resolve_browser_name(args.browser, elk_cfg)
        # Company-network fixed contract: ignore local proxy vars and connect ELK directly.
        session, cookie_host, cookie_count = build_session(api_base_url, browser, trust_env=False)
    except (CliError, ValueError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    attempts, success = run_query_once(
        session=session,
        api_base_url=api_base_url,
        endpoint_order=endpoint_order,
        index_pattern=index_pattern,
        es_query=es_query,
        timeout=args.timeout,
        network_mode="direct_no_proxy",
    )

    output: Dict[str, Any] = {
        "env": args.env,
        "mode": args.mode,
        "requestId": args.request_id,
        "targetId": args.target_id,
        "cmpId": clean_str(args.cmp_id),
        "timeWindow": {"gte": gte, "lte": lte},
        "configPath": str(config_path),
        "apiBaseUrl": api_base_url,
        "cookieHost": cookie_host,
        "cookieCount": cookie_count,
        "browser": browser,
        "proxyMode": "ignored_by_design",
        "proxyEnvKeysObserved": sorted(PROXY_ENV_KEYS),
        "indexPattern": index_pattern,
        "kql": kql,
        "guard": {"ok": kql_ok, "errors": kql_errors},
        "attempts": attempts,
    }

    if success is None:
        output["ok"] = False
        output["error"] = "All ELK API endpoints failed"
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2

    output["ok"] = True
    output["selectedEndpoint"] = success["endpoint"]
    output["httpStatus"] = success["httpStatus"]
    output["result"] = success["result"]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
