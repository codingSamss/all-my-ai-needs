#!/usr/bin/env python3
"""Image generation helper via configurable API providers (OpenAI-compat / Gemini)."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CODEX_HOME = os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex"))
CONFIG_PATH = os.path.join(CODEX_HOME, "skills", "image-gen", "providers.json")
DEFAULT_TIMEOUT = int(os.environ.get("IMAGE_GEN_TIMEOUT", "300"))
DEFAULT_PROXY = "http://127.0.0.1:7897"
DEFAULT_DEBUG_DIR = "/tmp/image-gen-debug"
_DEBUG_SEQ = 0


def _ensure_proxy() -> None:
    """Set default proxy if not already configured (matches top-level setup.sh)."""
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        if not os.environ.get(var):
            os.environ[var] = DEFAULT_PROXY


class ConfigError(RuntimeError):
    """Configuration error."""


class APIError(RuntimeError):
    """API request error."""


def _env_truthy(value: str | None) -> bool:
    """Interpret env-like truthy values."""
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _sanitize_url(url: str) -> str:
    """Mask sensitive query params in URL."""
    masked = re.sub(r"([?&]key=)[^&]+", r"\1***", url, flags=re.IGNORECASE)
    masked = re.sub(r"([?&]api_key=)[^&]+", r"\1***", masked, flags=re.IGNORECASE)
    return masked


def _sanitize_headers(headers: dict) -> dict:
    """Mask sensitive auth headers."""
    sanitized: dict = {}
    for key, value in headers.items():
        if str(key).strip().lower() == "authorization":
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def _resolve_debug_options(args: argparse.Namespace) -> tuple[bool, str]:
    """Resolve debug options from CLI args + env."""
    debug_raw = bool(getattr(args, "debug_raw", False))
    if not debug_raw:
        debug_raw = _env_truthy(os.environ.get("IMAGE_GEN_DEBUG_RAW"))
    debug_dir = (
        str(getattr(args, "debug_dir", "") or "").strip()
        or str(os.environ.get("IMAGE_GEN_DEBUG_DIR", "") or "").strip()
        or DEFAULT_DEBUG_DIR
    )
    return debug_raw, debug_dir


def _write_debug_json(
    *,
    enabled: bool,
    debug_dir: str,
    provider_key: str,
    endpoint: str,
    stage: str,
    payload: dict,
) -> str | None:
    """Write debug JSON payload to disk and return path."""
    if not enabled:
        return None
    safe_provider = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(provider_key or "unknown"))
    safe_endpoint = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(endpoint or "api"))
    safe_stage = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(stage or "stage"))
    ts_ms = int(time.time() * 1000)

    global _DEBUG_SEQ
    _DEBUG_SEQ += 1
    filename = f"{ts_ms}-{safe_provider}-{safe_endpoint}-{safe_stage}-{_DEBUG_SEQ}.json"

    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def _emit_debug_json(
    *,
    enabled: bool,
    debug_dir: str,
    provider_key: str,
    endpoint: str,
    stage: str,
    payload: dict,
) -> None:
    """Best-effort debug dump with stderr hint."""
    if not enabled:
        return
    try:
        path = _write_debug_json(
            enabled=enabled,
            debug_dir=debug_dir,
            provider_key=provider_key,
            endpoint=endpoint,
            stage=stage,
            payload=payload,
        )
        if path:
            print(f"[image-gen][debug] {stage}: {path}", file=sys.stderr)
    except Exception as exc:
        print(f"[image-gen][debug] 写入失败: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Diagram prompt templates
# ---------------------------------------------------------------------------

STYLE_HINTS = {
    "clean": "Use a clean, professional style with a white background, blue color scheme (#1a73e8, #4285f4, #e8f0fe), clear labels, consistent spacing, and anti-aliased rendering. Avoid clutter.",
    "detailed": "Use a detailed, information-rich style with a white background. Include annotations, data types, and descriptive labels. Use a professional blue/gray color palette with subtle gradients.",
    "minimal": "Use a minimalist style with a white background, thin lines, monochrome blue (#1a73e8) accents, generous whitespace, and minimal text. Focus on structure over decoration.",
}

DIAGRAM_TEMPLATES = {
    "architecture": (
        "Generate a professional software architecture diagram based on the following description. "
        "Layout: top-to-bottom or left-to-right, showing components as rounded rectangles with clear labels. "
        "Draw directed arrows between components to indicate data flow or dependencies, with labels on arrows where appropriate. "
        "{style} "
        "Output as a high-resolution PNG image.\n\n"
        "Architecture description:\n{input}"
    ),
    "flowchart": (
        "Generate a professional flowchart diagram based on the following description. "
        "Use standard flowchart shapes: rounded rectangles for start/end, rectangles for processes, diamonds for decisions. "
        "Draw directed arrows to show flow direction, with labels on decision branches (Yes/No). "
        "{style} "
        "Output as a high-resolution PNG image.\n\n"
        "Flowchart description:\n{input}"
    ),
    "sequence": (
        "Generate a professional UML sequence diagram based on the following description. "
        "Show participants as labeled boxes at the top with vertical lifelines. "
        "Draw horizontal arrows between lifelines for messages, with labels above arrows. "
        "Use solid arrows for synchronous calls, dashed arrows for responses. "
        "{style} "
        "Output as a high-resolution PNG image.\n\n"
        "Sequence description:\n{input}"
    ),
    "swimlane": (
        "Generate a professional swimlane (cross-functional) diagram based on the following description. "
        "Divide the diagram into horizontal or vertical lanes, each labeled with a role or system. "
        "Place process steps in the appropriate lane and connect them with directed arrows. "
        "{style} "
        "Output as a high-resolution PNG image.\n\n"
        "Swimlane description:\n{input}"
    ),
}

RATIO_HINTS = {
    "16:9": "The image should have a 16:9 aspect ratio (widescreen, landscape orientation).",
    "4:3": "The image should have a 4:3 aspect ratio (standard, landscape orientation).",
    "1:1": "The image should have a 1:1 aspect ratio (square).",
    "9:16": "The image should have a 9:16 aspect ratio (portrait, vertical orientation).",
    "3:4": "The image should have a 3:4 aspect ratio (portrait orientation).",
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load providers.json config."""
    if not os.path.isfile(CONFIG_PATH):
        raise ConfigError(f"配置文件不存在: {CONFIG_PATH}\n请先运行 setup.sh image-gen")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    """Save providers.json config."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_active_provider(cfg: dict) -> tuple[str, dict]:
    """Return (key, provider_dict) for the active provider."""
    active = cfg.get("active", "")
    providers = cfg.get("providers", {})
    if active not in providers:
        raise ConfigError(f"active provider '{active}' 不存在于 providers 列表中")
    return active, providers[active]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def http_post_json(
    url: str,
    headers: dict,
    body: dict,
    *,
    debug_raw: bool = False,
    debug_dir: str = DEFAULT_DEBUG_DIR,
    provider_key: str = "unknown",
    endpoint: str = "api",
) -> dict:
    """POST JSON and return parsed response."""
    sanitized_url = _sanitize_url(url)
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")

    _emit_debug_json(
        enabled=debug_raw,
        debug_dir=debug_dir,
        provider_key=provider_key,
        endpoint=endpoint,
        stage="request",
        payload={
            "url": sanitized_url,
            "headers": _sanitize_headers(headers),
            "body": body,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw_text = resp.read().decode("utf-8", errors="replace")
            _emit_debug_json(
                enabled=debug_raw,
                debug_dir=debug_dir,
                provider_key=provider_key,
                endpoint=endpoint,
                stage="response",
                payload={
                    "url": sanitized_url,
                    "status": getattr(resp, "status", None),
                    "reason": getattr(resp, "reason", None),
                    "body_text": raw_text,
                },
            )
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise APIError(f"响应不是合法 JSON。响应内容:\n{raw_text[:500]}") from exc
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_debug_json(
            enabled=debug_raw,
            debug_dir=debug_dir,
            provider_key=provider_key,
            endpoint=endpoint,
            stage="http_error",
            payload={
                "url": sanitized_url,
                "status": exc.code,
                "reason": str(exc.reason) if getattr(exc, "reason", None) else None,
                "body_text": body_text,
            },
        )
        raise APIError(f"HTTP {exc.code}: {body_text[:500]}") from exc
    except (TimeoutError, socket.timeout) as exc:
        _emit_debug_json(
            enabled=debug_raw,
            debug_dir=debug_dir,
            provider_key=provider_key,
            endpoint=endpoint,
            stage="timeout",
            payload={
                "url": sanitized_url,
                "timeout_seconds": DEFAULT_TIMEOUT,
                "error": str(exc),
            },
        )
        raise APIError(
            f"请求超时（>{DEFAULT_TIMEOUT}s）: {url}. "
            "可尝试增大 IMAGE_GEN_TIMEOUT 环境变量。"
        ) from exc
    except urllib.error.URLError as exc:
        _emit_debug_json(
            enabled=debug_raw,
            debug_dir=debug_dir,
            provider_key=provider_key,
            endpoint=endpoint,
            stage="network_error",
            payload={
                "url": sanitized_url,
                "error": str(exc.reason),
            },
        )
        raise APIError(f"网络错误: {exc.reason}") from exc


def download_url(url: str) -> bytes:
    """Download binary content from URL."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return resp.read()
    except (TimeoutError, socket.timeout) as exc:
        raise APIError(
            f"下载超时（>{DEFAULT_TIMEOUT}s）: {url}. "
            "可尝试增大 IMAGE_GEN_TIMEOUT 环境变量。"
        ) from exc
    except urllib.error.URLError as exc:
        raise APIError(f"下载失败: {exc}") from exc


# ---------------------------------------------------------------------------
# API call: OpenAI-compatible format
# ---------------------------------------------------------------------------

def call_openai(
    provider_key: str,
    provider: dict,
    prompt: str,
    *,
    debug_raw: bool = False,
    debug_dir: str = DEFAULT_DEBUG_DIR,
) -> bytes:
    """Call OpenAI-compatible chat completions API and return image bytes."""
    url = f"{provider['base_url'].rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {provider['api_key']}"}
    body = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = http_post_json(
        url,
        headers,
        body,
        debug_raw=debug_raw,
        debug_dir=debug_dir,
        provider_key=provider_key,
        endpoint="chat_completions",
    )

    # Extract image from response
    choices = resp.get("choices", [])
    if not choices:
        raise APIError(f"API 返回空 choices: {json.dumps(resp, ensure_ascii=False)[:300]}")

    content = choices[0].get("message", {}).get("content", "")

    # Case 1: content is a list (multimodal response)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                # inline base64 image
                if part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:"):
                        b64 = img_url.split(",", 1)[1]
                        return base64.b64decode(b64)
                    elif img_url:
                        return download_url(img_url)
                # inline_data style
                if part.get("type") == "image" and part.get("data"):
                    return base64.b64decode(part["data"])
        raise APIError(f"未在 content 列表中找到图片: {json.dumps(content, ensure_ascii=False)[:300]}")

    # Case 2: content is a string - look for URLs or base64
    if isinstance(content, str):
        # Check for markdown image syntax ![...](url)
        md_match = re.search(r'!\[.*?\]\((https?://\S+)\)', content)
        if md_match:
            return download_url(md_match.group(1))
        # Check for bare URL
        url_match = re.search(r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif))', content, re.IGNORECASE)
        if url_match:
            return download_url(url_match.group(1))
        # Check for base64 data
        b64_match = re.search(r'data:image/\w+;base64,([A-Za-z0-9+/=]+)', content)
        if b64_match:
            return base64.b64decode(b64_match.group(1))
        raise APIError(f"未在响应中找到图片。响应内容:\n{content[:500]}")

    raise APIError(f"未预期的 content 类型: {type(content)}")


# ---------------------------------------------------------------------------
# API call: Google Gemini native format
# ---------------------------------------------------------------------------

def call_gemini(
    provider_key: str,
    provider: dict,
    prompt: str,
    *,
    debug_raw: bool = False,
    debug_dir: str = DEFAULT_DEBUG_DIR,
) -> bytes:
    """Call Google Gemini generateContent API and return image bytes."""
    model = provider["model"]
    base = provider["base_url"].rstrip("/")
    api_key = provider["api_key"]
    url = f"{base}/models/{model}:generateContent?key={api_key}"
    headers = {}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    resp = http_post_json(
        url,
        headers,
        body,
        debug_raw=debug_raw,
        debug_dir=debug_dir,
        provider_key=provider_key,
        endpoint="gemini_generate_content",
    )

    # Extract image from Gemini response
    candidates = resp.get("candidates", [])
    if not candidates:
        raise APIError(f"Gemini 返回空 candidates: {json.dumps(resp, ensure_ascii=False)[:300]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    raise APIError(f"未在 Gemini 响应中找到图片: {json.dumps(parts, ensure_ascii=False)[:300]}")


# ---------------------------------------------------------------------------
# High-level generate
# ---------------------------------------------------------------------------

def generate_image(
    prompt: str,
    output: str | None = None,
    *,
    debug_raw: bool = False,
    debug_dir: str = DEFAULT_DEBUG_DIR,
) -> str:
    """Generate image from prompt and save to file. Return output path."""
    cfg = load_config()
    key, provider = get_active_provider(cfg)

    api_key = provider.get("api_key", "")
    if not api_key:
        raise ConfigError(f"provider '{key}' 的 api_key 为空，请编辑 {CONFIG_PATH}")

    fmt = provider.get("format", "openai")
    print(f"[image-gen] 使用 provider: {provider.get('name', key)} ({fmt})", file=sys.stderr)
    print(f"[image-gen] 模型: {provider.get('model', 'unknown')}", file=sys.stderr)
    if debug_raw:
        print(f"[image-gen][debug] raw dump 目录: {debug_dir}", file=sys.stderr)
    print(f"[image-gen] 生成中...", file=sys.stderr)

    if fmt == "gemini":
        img_bytes = call_gemini(
            key,
            provider,
            prompt,
            debug_raw=debug_raw,
            debug_dir=debug_dir,
        )
    else:
        img_bytes = call_openai(
            key,
            provider,
            prompt,
            debug_raw=debug_raw,
            debug_dir=debug_dir,
        )

    if output is None:
        ts = int(time.time())
        output = f"/tmp/image-gen-{ts}.png"

    with open(output, "wb") as f:
        f.write(img_bytes)

    size_kb = len(img_bytes) / 1024
    print(f"[image-gen] 图片已保存: {output} ({size_kb:.1f} KB)", file=sys.stderr)
    return output


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_config(args: argparse.Namespace) -> int:
    """Show or update config."""
    cfg = load_config()

    if args.switch:
        target = args.switch
        providers = cfg.get("providers", {})
        if target not in providers:
            print(f"[ERROR] provider '{target}' 不存在。可选: {', '.join(providers.keys())}", file=sys.stderr)
            return 1
        cfg["active"] = target
        save_config(cfg)
        print(f"已切换 active provider 为: {target}")
        return 0

    # Show current config
    active = cfg.get("active", "")
    providers = cfg.get("providers", {})
    print(f"配置文件: {CONFIG_PATH}")
    print(f"Active provider: {active}")
    print()
    for k, v in providers.items():
        marker = " <-- active" if k == active else ""
        key_status = "已配置" if v.get("api_key") else "未配置"
        print(f"  [{k}]{marker}")
        print(f"    名称: {v.get('name', '')}")
        print(f"    Base URL: {v.get('base_url', '')}")
        print(f"    模型: {v.get('model', '')}")
        print(f"    格式: {v.get('format', '')}")
        print(f"    API Key: {key_status}")
        print()
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Free-form image generation."""
    prompt = args.prompt
    # Add ratio and style hints
    extras = []
    ratio = getattr(args, "ratio", "16:9")
    if ratio in RATIO_HINTS:
        extras.append(RATIO_HINTS[ratio])
    style = getattr(args, "style", "clean")
    if style in STYLE_HINTS:
        extras.append(STYLE_HINTS[style])
    if extras:
        prompt = prompt + "\n\n" + " ".join(extras)

    debug_raw, debug_dir = _resolve_debug_options(args)
    output = generate_image(
        prompt,
        getattr(args, "output", None),
        debug_raw=debug_raw,
        debug_dir=debug_dir,
    )
    # Print path to stdout for Claude to pick up
    print(output)
    return 0


def cmd_diagram(args: argparse.Namespace) -> int:
    """Structured diagram generation."""
    diagram_type = args.type
    if diagram_type not in DIAGRAM_TEMPLATES:
        print(f"[ERROR] 不支持的图表类型: {diagram_type}", file=sys.stderr)
        print(f"可选类型: {', '.join(DIAGRAM_TEMPLATES.keys())}", file=sys.stderr)
        return 1

    # Get input text
    if args.file:
        if not os.path.isfile(args.file):
            print(f"[ERROR] 文件不存在: {args.file}", file=sys.stderr)
            return 1
        with open(args.file, "r", encoding="utf-8") as f:
            input_text = f.read().strip()
    elif args.input:
        input_text = args.input
    else:
        print("[ERROR] 需要 --input 或 --file 参数", file=sys.stderr)
        return 1

    # Build prompt from template
    style = getattr(args, "style", "clean")
    style_hint = STYLE_HINTS.get(style, STYLE_HINTS["clean"])
    ratio = getattr(args, "ratio", "16:9")
    ratio_hint = RATIO_HINTS.get(ratio, "")

    prompt = DIAGRAM_TEMPLATES[diagram_type].format(style=style_hint, input=input_text)
    if ratio_hint:
        prompt += "\n\n" + ratio_hint

    debug_raw, debug_dir = _resolve_debug_options(args)
    output = generate_image(
        prompt,
        getattr(args, "output", None),
        debug_raw=debug_raw,
        debug_dir=debug_dir,
    )
    print(output)
    return 0


# ---------------------------------------------------------------------------
# Argparse setup
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Image generation via configurable API providers",
        prog="image-gen",
    )
    sub = p.add_subparsers(dest="subcommand", required=True)

    # config
    s = sub.add_parser("config", help="查看或切换 provider 配置")
    s.add_argument("--switch", metavar="PROVIDER", help="切换 active provider")
    s.set_defaults(func=cmd_config)

    # generate
    s = sub.add_parser("generate", help="自由生图")
    s.add_argument("prompt", help="图片描述 prompt")
    s.add_argument("--output", "-o", help="输出文件路径")
    s.add_argument("--ratio", default="16:9", help="宽高比 (默认 16:9)")
    s.add_argument("--style", default="clean", choices=["clean", "detailed", "minimal"], help="风格 (默认 clean)")
    s.add_argument("--debug-raw", action="store_true", help="落盘保存原始请求/响应 JSON 以便排查")
    s.add_argument("--debug-dir", help=f"调试文件目录 (默认 {DEFAULT_DEBUG_DIR})")
    s.set_defaults(func=cmd_generate)

    # diagram
    s = sub.add_parser("diagram", help="结构化图表生成")
    s.add_argument("--type", "-t", required=True, choices=["architecture", "flowchart", "sequence", "swimlane"], help="图表类型")
    s.add_argument("--input", "-i", help="图表描述文本")
    s.add_argument("--file", "-f", help="从文件读取图表描述")
    s.add_argument("--output", "-o", help="输出文件路径")
    s.add_argument("--ratio", default="16:9", help="宽高比 (默认 16:9)")
    s.add_argument("--style", default="clean", choices=["clean", "detailed", "minimal"], help="风格 (默认 clean)")
    s.add_argument("--debug-raw", action="store_true", help="落盘保存原始请求/响应 JSON 以便排查")
    s.add_argument("--debug-dir", help=f"调试文件目录 (默认 {DEFAULT_DEBUG_DIR})")
    s.set_defaults(func=cmd_diagram)

    return p


def main() -> int:
    """CLI entry point."""
    _ensure_proxy()
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 1
    except APIError as exc:
        print(f"[API ERROR] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n[ERROR] 用户中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
