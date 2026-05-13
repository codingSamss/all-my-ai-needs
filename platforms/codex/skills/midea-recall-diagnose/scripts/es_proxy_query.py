#!/usr/bin/env python3
"""Query Elasticsearch through the configured ES console transport without Playwright."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from prepare_diagnosis import clean_str, ensure_dict, load_env_config, resolve_es_console_route


VALID_ENVS = ("sit", "uat", "prod")
VALID_BROWSERS = ("chrome", "chromium", "edge", "firefox", "brave")
VALID_METHODS = ("GET", "POST", "PUT", "DELETE")
VALID_TRANSPORTS = ("auto", "kibana_console_proxy", "zhongli_cloud_proxy")
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
    """Raised when proxy querying fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, choices=VALID_ENVS)
    parser.add_argument("--config", default=None, help="Path to env-config.local.yaml/json")
    parser.add_argument("--source-system", default=None, help="Optional sourceSystem route disambiguator")
    parser.add_argument("--request-dsl", default=None, help="ELK requestDsl JSON string or raw TRACE_TARGET_ES line")
    parser.add_argument("--request-dsl-file", default=None, help="File containing requestDsl or a raw ELK line")
    parser.add_argument("--route-json", default=None, help="Inline esConsoleRoute JSON from prepare_diagnosis.py")
    parser.add_argument("--route-file", default=None, help="File containing esConsoleRoute JSON")
    parser.add_argument("--path", required=True, help="ES proxy path, for example /index/_search")
    parser.add_argument("--method", default="POST", choices=VALID_METHODS)
    parser.add_argument("--body", default=None, help="ES request body JSON string")
    parser.add_argument("--body-file", default=None, help="File containing ES request body JSON")
    parser.add_argument("--raw-body", action="store_true", help="Send body text without JSON validation")
    parser.add_argument("--browser", choices=VALID_BROWSERS, default=None)
    parser.add_argument("--cookie-domain", default=None, help="Override browser cookie lookup domain")
    parser.add_argument(
        "--transport",
        choices=VALID_TRANSPORTS,
        default="auto",
        help="ES execution transport. auto uses prod=zhongli_cloud_proxy and sit/uat=kibana_console_proxy unless config overrides it.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--check-url-templates", action="store_true")
    parser.add_argument("--use-proxy-env", action="store_true", help="Honor local proxy environment variables")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print proxy payload without network I/O")
    return parser.parse_args()


def resolve_default_config() -> Path:
    base = SCRIPT_DIR.parent / "references"
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


def load_json_arg(inline_value: Optional[str], file_value: Optional[str], field: str) -> Optional[Dict[str, Any]]:
    text: Optional[str] = None
    if file_value:
        text = Path(file_value).read_text(encoding="utf-8")
    elif inline_value:
        text = inline_value
    if text is None:
        return None
    try:
        return ensure_dict(json.loads(text), field)
    except json.JSONDecodeError as exc:
        raise CliError(f"invalid {field} JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def load_text_arg(inline_value: Optional[str], file_value: Optional[str], field: str) -> Optional[str]:
    if file_value:
        return Path(file_value).read_text(encoding="utf-8")
    value = clean_str(inline_value)
    if value:
        return value
    return None


def normalize_proxy_path(path: str) -> str:
    value = clean_str(path)
    if not value:
        raise CliError("--path is required")
    if not value.startswith("/"):
        value = f"/{value}"
    return value


def normalize_body_text(args: argparse.Namespace) -> str:
    raw = load_text_arg(args.body, args.body_file, "body")
    if raw is None:
        return ""
    if args.raw_body:
        return raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(
            f"invalid --body JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
            "Use --raw-body only if the console proxy expects non-JSON text."
        ) from exc
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def ensure_url(value: Any, field: str) -> str:
    url = clean_str(value)
    if not url:
        raise CliError(f"{field} is required")
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise CliError(f"Invalid {field}: {url}")
    return url


def origin_from_url(value: Any, field: str) -> str:
    url = ensure_url(value, field)
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def contains_placeholder(value: Any) -> bool:
    text = clean_str(value)
    return not text or "<" in text or ">" in text


def env_es_console(env_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return ensure_dict(env_cfg.get("es_console"), "env.es_console")


def route_base_from_env(env_cfg: Dict[str, Any]) -> Dict[str, Any]:
    es_console = env_es_console(env_cfg)
    route: Dict[str, Any] = {}
    for key in (
        "transport",
        "console_base_url",
        "console_proxy_url",
        "request_proxy_url",
        "cookie_browser",
        "cookie_domain",
    ):
        value = clean_str(es_console.get(key))
        if value:
            route[key] = value
    return route


def enrich_route_from_env(route: Dict[str, Any], env_cfg: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(route)
    for key, value in route_base_from_env(env_cfg).items():
        if key not in enriched:
            enriched[key] = value
    return enriched


def resolve_browser_name(cli_browser: Optional[str], env_cfg: Dict[str, Any]) -> str:
    es_console = env_es_console(env_cfg)
    elk_cfg = ensure_dict(env_cfg.get("elk"), "env.elk")
    browser = (
        clean_str(cli_browser)
        or clean_str(es_console.get("cookie_browser"))
        or clean_str(elk_cfg.get("cookie_browser"))
        or "chrome"
    )
    if browser not in VALID_BROWSERS:
        raise CliError(f"Unsupported browser: {browser}")
    return browser


def resolve_transport(cli_transport: str, env: str, env_cfg: Dict[str, Any], route: Dict[str, Any]) -> str:
    if cli_transport != "auto":
        return cli_transport
    configured = clean_str(route.get("transport")) or clean_str(env_es_console(env_cfg).get("transport"))
    if configured:
        if configured not in VALID_TRANSPORTS or configured == "auto":
            raise CliError(f"Unsupported es_console.transport: {configured}")
        return configured
    return "zhongli_cloud_proxy" if env == "prod" else "kibana_console_proxy"


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


def build_session(
    proxy_url: str,
    browser: str,
    *,
    cookie_domain: Optional[str],
    trust_env: bool,
) -> Tuple[requests.Session, str, int]:
    parsed = urlsplit(proxy_url)
    hostname = clean_str(parsed.hostname)
    if not hostname:
        raise CliError(f"Invalid proxy URL: {proxy_url}")
    cookie_host = clean_str(cookie_domain) or hostname
    jar = load_browser_cookies(cookie_host, browser)
    cookie_count = sum(1 for _ in jar)
    session = requests.Session()
    session.trust_env = trust_env
    session.cookies = jar
    return session, cookie_host, cookie_count


def route_from_args(args: argparse.Namespace, env_cfg: Dict[str, Any], config_path: Path) -> Dict[str, Any]:
    route = load_json_arg(args.route_json, args.route_file, "esConsoleRoute")
    if route is not None:
        return enrich_route_from_env(route, env_cfg)

    request_dsl = load_text_arg(args.request_dsl, args.request_dsl_file, "requestDsl")
    es_console = env_es_console(env_cfg)
    configured_transport = clean_str(es_console.get("transport"))
    if (configured_transport == "kibana_console_proxy" or args.env in ("sit", "uat")) and not es_console.get("cluster_routes"):
        return route_base_from_env(env_cfg)

    if not request_dsl and not clean_str(args.source_system):
        if configured_transport == "kibana_console_proxy" or args.env in ("sit", "uat"):
            return route_base_from_env(env_cfg)
        raise CliError(
            "ES route requires --route-json/--route-file, or --request-dsl/--request-dsl-file, "
            "or --source-system"
        )
    try:
        resolved = resolve_es_console_route(
            env_cfg,
            clean_str(args.source_system),
            request_dsl,
            str(config_path),
        )
    except SystemExit as exc:
        if configured_transport == "kibana_console_proxy" or args.env in ("sit", "uat"):
            fallback = route_base_from_env(env_cfg)
            fallback["routeWarning"] = str(exc)
            return fallback
        raise CliError(str(exc)) from exc
    if not resolved:
        raise CliError("unable to resolve ES console route")
    return enrich_route_from_env(resolved, env_cfg)


def resolve_zhongli_proxy_url(route: Dict[str, Any]) -> str:
    proxy_url = clean_str(route.get("request_proxy_url"))
    if not proxy_url:
        raise CliError("PROD_ES_PROXY_NOT_CONFIGURED: esConsoleRoute.request_proxy_url is required")
    if contains_placeholder(proxy_url):
        raise CliError(f"PROD_ES_PROXY_NOT_CONFIGURED: request_proxy_url still contains placeholder: {proxy_url}")
    return ensure_url(proxy_url, "request_proxy_url")


def resolve_kibana_proxy_url(route: Dict[str, Any]) -> str:
    explicit = clean_str(route.get("console_proxy_url"))
    if explicit:
        if contains_placeholder(explicit):
            raise CliError(f"console_proxy_url still contains placeholder: {explicit}")
        return ensure_url(explicit, "console_proxy_url")

    base = clean_str(route.get("console_base_url")) or clean_str(route.get("page_url"))
    if not base:
        raise CliError("kibana_console_proxy requires es_console.console_base_url or console_proxy_url")
    origin = origin_from_url(base, "console_base_url")
    return f"{origin}/api/console/proxy"


def resolve_proxy_url(route: Dict[str, Any], transport: str) -> str:
    if transport == "kibana_console_proxy":
        return resolve_kibana_proxy_url(route)
    if transport == "zhongli_cloud_proxy":
        return resolve_zhongli_proxy_url(route)
    raise CliError(f"Unsupported transport: {transport}")


def resolve_cins_id(route: Dict[str, Any]) -> str:
    cins_id = clean_str(route.get("cinsId")) or clean_str(route.get("cins_id")) or clean_str(route.get("instance_id"))
    if not cins_id:
        raise CliError("esConsoleRoute.instance_id/cinsId is required")
    return cins_id


def zhongli_request_headers(proxy_url: str, route: Dict[str, Any]) -> Dict[str, str]:
    parsed = urlsplit(proxy_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": origin,
    }
    page_url = clean_str(route.get("page_url"))
    if page_url:
        headers["referer"] = page_url
    return headers


def kibana_request_headers() -> Dict[str, str]:
    return {
        "content-type": "application/json",
        "kbn-xsrf": "true",
    }


def maybe_parse_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def unwrap_response(payload: Any) -> Any:
    current = maybe_parse_json(payload)
    for key in ("data", "result", "response"):
        if isinstance(current, dict) and key in current:
            nested = current.get(key)
            if isinstance(nested, (dict, list)):
                current = nested
                break
            parsed = maybe_parse_json(nested)
            if parsed is not nested:
                current = parsed
                break
    return current


def summarize_es_payload(payload: Any) -> Dict[str, Any]:
    raw = unwrap_response(payload)
    if not isinstance(raw, dict):
        return {"parsed": isinstance(raw, (dict, list))}

    hits = raw.get("hits")
    if isinstance(hits, dict):
        total_raw = hits.get("total")
        total = total_raw.get("value") if isinstance(total_raw, dict) else total_raw
        returned_hits = hits.get("hits")
        returned = len(returned_hits) if isinstance(returned_hits, list) else None
        return {
            "tookMs": raw.get("took"),
            "timedOut": raw.get("timed_out"),
            "total": total,
            "returned": returned,
        }

    if "count" in raw:
        return {"count": raw.get("count")}

    return {"keys": sorted(str(key) for key in raw.keys())[:20]}


def check_url_templates(
    session: requests.Session,
    proxy_url: str,
    cins_id: str,
    headers: Dict[str, str],
    timeout: float,
) -> Dict[str, Any]:
    prefix = proxy_url.rsplit("/", 1)[0]
    url = f"{prefix}/urlTemplates"
    response = session.get(url, params={"cinsId": cins_id}, headers=headers, timeout=timeout)
    body_preview = response.text[:500]
    return {
        "url": url,
        "httpStatus": response.status_code,
        "ok": response.status_code < 400,
        "bodyPreview": body_preview,
    }


def body_text_to_payload(body_text: str) -> Any:
    text = body_text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return body_text


def query_kibana_console_proxy(
    session: requests.Session,
    proxy_url: str,
    path: str,
    method: str,
    body_text: str,
    timeout: float,
) -> Dict[str, Any]:
    params = {
        "path": path,
        "method": method,
    }
    request_body = body_text_to_payload(body_text)
    response = session.post(
        proxy_url,
        params=params,
        headers=kibana_request_headers(),
        json=request_body,
        timeout=timeout,
    )
    raw_text = response.text[:1000]
    if response.status_code >= 400:
        raise QueryError(f"HTTP {response.status_code} from kibana console proxy: {raw_text}")
    try:
        response_payload = response.json()
    except json.JSONDecodeError as exc:
        raise QueryError(f"Non-JSON response from kibana console proxy: {raw_text}") from exc
    return {
        "httpStatus": response.status_code,
        "requestPayload": {
            "params": params,
            "body": request_body,
        },
        "response": response_payload,
        "summary": summarize_es_payload(response_payload),
    }


def query_zhongli_cloud_proxy(
    session: requests.Session,
    proxy_url: str,
    route: Dict[str, Any],
    path: str,
    method: str,
    body_text: str,
    timeout: float,
) -> Dict[str, Any]:
    cins_id = resolve_cins_id(route)
    headers = zhongli_request_headers(proxy_url, route)
    payload = {
        "cinsId": cins_id,
        "path": path,
        "method": method,
        "body": body_text,
    }
    response = session.post(proxy_url, headers=headers, json=payload, timeout=timeout)
    raw_text = response.text[:1000]
    if response.status_code >= 400:
        raise QueryError(f"HTTP {response.status_code} from requestEs: {raw_text}")
    try:
        response_payload = response.json()
    except json.JSONDecodeError as exc:
        raise QueryError(f"Non-JSON response from requestEs: {raw_text}") from exc
    return {
        "httpStatus": response.status_code,
        "requestPayload": payload,
        "response": response_payload,
        "summary": summarize_es_payload(response_payload),
    }


def query_es_proxy(
    session: requests.Session,
    proxy_url: str,
    route: Dict[str, Any],
    transport: str,
    path: str,
    method: str,
    body_text: str,
    timeout: float,
) -> Dict[str, Any]:
    if transport == "kibana_console_proxy":
        return query_kibana_console_proxy(
            session=session,
            proxy_url=proxy_url,
            path=path,
            method=method,
            body_text=body_text,
            timeout=timeout,
        )
    if transport == "zhongli_cloud_proxy":
        return query_zhongli_cloud_proxy(
            session=session,
            proxy_url=proxy_url,
            route=route,
            path=path,
            method=method,
            body_text=body_text,
            timeout=timeout,
        )
    raise CliError(f"Unsupported transport: {transport}")


def main() -> int:
    args = parse_args()
    try:
        config_path = Path(args.config) if args.config else resolve_default_config()
        if not config_path.exists():
            raise CliError(f"Config not found: {config_path}")
        env_cfg = load_env_config(str(config_path), args.env)
        route = route_from_args(args, env_cfg, config_path)
        transport = resolve_transport(args.transport, args.env, env_cfg, route)
        path = normalize_proxy_path(args.path)
        body_text = normalize_body_text(args)
        browser = resolve_browser_name(args.browser, env_cfg)
        proxy_url_error: Optional[str] = None
        try:
            proxy_url = resolve_proxy_url(route, transport)
        except CliError as exc:
            if not args.dry_run:
                raise
            proxy_url = None
            proxy_url_error = str(exc)
        cins_id = resolve_cins_id(route) if transport == "zhongli_cloud_proxy" else None
    except (CliError, OSError, ValueError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    output: Dict[str, Any] = {
        "env": args.env,
        "configPath": str(config_path),
        "transport": transport,
        "route": {
            "cluster": route.get("cluster"),
            "resolved_by": route.get("resolved_by"),
            "matched_indices": route.get("matched_indices"),
            "instance_id": route.get("instance_id"),
            "region_id": route.get("region_id"),
            "zone": route.get("zone"),
            "page_url": route.get("page_url"),
            "routeWarning": route.get("routeWarning"),
        },
        "proxyUrl": proxy_url,
        "proxyUrlError": proxy_url_error,
        "cinsId": cins_id,
        "path": path,
        "method": args.method,
        "browser": browser,
        "proxyMode": "ignored_by_default" if not args.use_proxy_env else "honor_env",
        "proxyEnvKeysObserved": sorted(PROXY_ENV_KEYS),
    }

    if args.dry_run:
        output["ok"] = True
        output["dryRun"] = True
        if transport == "zhongli_cloud_proxy":
            output["requestPayload"] = {
                "cinsId": cins_id,
                "path": path,
                "method": args.method,
                "body": body_text,
            }
        else:
            output["requestPayload"] = {
                "params": {
                    "path": path,
                    "method": args.method,
                },
                "body": body_text_to_payload(body_text),
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    try:
        session, cookie_host, cookie_count = build_session(
            proxy_url,
            browser,
            cookie_domain=args.cookie_domain or clean_str(route.get("cookie_domain")),
            trust_env=bool(args.use_proxy_env),
        )
        output["cookieHost"] = cookie_host
        output["cookieCount"] = cookie_count
    except (CliError, OSError) as exc:
        output["ok"] = False
        output["error"] = str(exc)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2

    if args.check_url_templates and transport == "zhongli_cloud_proxy":
        try:
            output["urlTemplatesCheck"] = check_url_templates(
                session,
                proxy_url,
                cins_id,
                zhongli_request_headers(proxy_url, route),
                args.timeout,
            )
        except requests.RequestException as exc:
            output["urlTemplatesCheck"] = {"ok": False, "error": str(exc)}
    elif args.check_url_templates:
        output["urlTemplatesCheck"] = {"skipped": True, "reason": "urlTemplates is only available for zhongli_cloud_proxy"}

    try:
        result = query_es_proxy(
            session=session,
            proxy_url=proxy_url,
            route=route,
            transport=transport,
            path=path,
            method=args.method,
            body_text=body_text,
            timeout=args.timeout,
        )
    except (requests.RequestException, QueryError, CliError) as exc:
        output["ok"] = False
        output["error"] = str(exc)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2

    output["ok"] = True
    output.update(result)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
