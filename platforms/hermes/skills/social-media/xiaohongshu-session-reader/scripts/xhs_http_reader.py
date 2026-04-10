#!/usr/bin/env python3
"""Stable Xiaohongshu reader: HTTP-first with explicit browser-fallback signals."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import html
import json
import os
import re
import ssl
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class XhsReadError(RuntimeError):
    """Raised when HTTP read pipeline fails."""


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

HTML_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
JSON_ACCEPT = "application/json, text/plain, */*"
CAPTCHA_PATTERNS = (
    "Security Verification",
    "/website-login/captcha",
    "验证",
)
NOTE_ID_RE = re.compile(r"/explore/([0-9a-f]{24,})|/user/profile/[^/]+/([0-9a-f]{24,})")
PROFILE_UID_RE = re.compile(r"/user/profile/([^/?#]+)")
NOTE_SECTION_RE = re.compile(r'<section class="note-item".*?</section>', re.S)
DEFAULT_CA_CANDIDATES = ("/etc/ssl/cert.pem",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Xiaohongshu HTTP-first reader (profile cards / note detail)."
    )
    parser.add_argument("--url", required=True, help="xhslink / xiaohongshu profile or note URL")
    parser.add_argument(
        "--mode",
        choices=("auto", "profile", "note"),
        default="auto",
        help="Read mode. Default: auto",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=40,
        help="Max profile note cards to return. Default: 40",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=20,
        help="Max comments to return when API is available. Default: 20",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout (seconds). Default: 20",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="HTTP retries on transient errors. Default: 2",
    )
    parser.add_argument("--output", help="Write JSON output to file path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument(
        "--chrome-profile",
        default="Default",
        help='Chrome profile name for cookie extraction. Default: "Default"',
    )
    parser.add_argument(
        "--chrome-profile-dir",
        help="Chrome profile root dir or direct Cookies DB path",
    )
    parser.add_argument("--debug", action="store_true", help="Include debug fields in output")
    return parser.parse_args()


def resolve_cookie_db(profile: str, profile_dir: str | None) -> Path:
    if profile_dir:
        root = Path(profile_dir).expanduser()
        if root.is_file():
            return root
        candidates = [
            root / "Cookies",
            root / profile / "Cookies",
            root / "Default" / "Cookies",
        ]
        for path in candidates:
            if path.is_file():
                return path
        raise XhsReadError(f"Cannot find Cookies DB under: {root}")

    base = Path("~/Library/Application Support/Google/Chrome").expanduser()
    db_path = base / profile / "Cookies"
    if db_path.is_file():
        return db_path
    if profile != "Default":
        fallback = base / "Default" / "Cookies"
        if fallback.is_file():
            return fallback
    raise XhsReadError(f"Chrome Cookies DB not found: {db_path}")


def get_chrome_keychain_password() -> bytes:
    service_names = ["Chrome Safe Storage", "Chromium Safe Storage"]
    for service in service_names:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-w"],
                check=True,
                capture_output=True,
                text=True,
            )
            password = result.stdout.strip()
            if password:
                return password.encode("utf-8")
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    raise XhsReadError("Cannot read Chrome Safe Storage password from Keychain")


def derive_chrome_aes_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def aes_cbc_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    lib_path = ctypes.util.find_library("System")
    if not lib_path:
        raise XhsReadError("Cannot load macOS System library for CommonCrypto")
    lib = ctypes.cdll.LoadLibrary(lib_path)
    iv = b" " * 16
    buf = ctypes.create_string_buffer(len(ciphertext) + 16)
    moved = ctypes.c_size_t(0)
    status = lib.CCCrypt(
        1,
        0,
        1,
        key,
        len(key),
        iv,
        ciphertext,
        len(ciphertext),
        buf,
        len(ciphertext) + 16,
        ctypes.byref(moved),
    )
    if status != 0:
        raise XhsReadError(f"CCCrypt decrypt failed, status={status}")
    return buf.raw[: moved.value]


def decrypt_cookie_value(key: bytes, plain_value: str, encrypted_value: bytes) -> str:
    value = (plain_value or "").strip()
    if value:
        return value
    if not encrypted_value:
        return ""
    if encrypted_value.startswith((b"v10", b"v11")):
        decrypted = aes_cbc_decrypt(key, encrypted_value[3:])
        if len(decrypted) > 32:
            tail = decrypted[32:]
            text = tail.decode("utf-8", errors="ignore").strip("\x00")
            if text:
                return text
        return decrypted.decode("utf-8", errors="ignore").strip("\x00")
    return encrypted_value.decode("utf-8", errors="ignore").strip("\x00")


def load_xhs_cookies(profile: str, profile_dir: str | None) -> dict[str, str]:
    db_path = resolve_cookie_db(profile, profile_dir)
    key = derive_chrome_aes_key(get_chrome_keychain_password())

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        subprocess.run(["cp", str(db_path), tmp_path], check=True, capture_output=True)
        conn = sqlite3.connect(tmp_path)
        rows = conn.execute(
            """
            SELECT name, value, encrypted_value, host_key, last_access_utc
            FROM cookies
            WHERE host_key LIKE '%xiaohongshu.com'
            ORDER BY last_access_utc DESC
            """
        ).fetchall()
        conn.close()
    except (subprocess.CalledProcessError, sqlite3.Error) as exc:
        raise XhsReadError(f"Failed to read Chrome cookies: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not rows:
        raise XhsReadError("No xiaohongshu.com cookies found in Chrome profile")

    picked: dict[str, str] = {}
    for name, value, encrypted, host, _access in rows:
        cookie_name = str(name or "").strip()
        if not cookie_name or cookie_name in picked:
            continue
        if not str(host or "").endswith("xiaohongshu.com"):
            continue
        try:
            plain = decrypt_cookie_value(key, str(value or ""), encrypted or b"")
        except XhsReadError:
            continue
        if not plain:
            continue
        picked[cookie_name] = plain

    if not picked:
        raise XhsReadError("Failed to decrypt xiaohongshu.com cookies")
    return picked


def cookie_header_from_map(cookie_map: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in sorted(cookie_map.items()))


def detect_captcha(url: str, text: str) -> bool:
    merged = f"{url}\n{text[:2000]}"
    return any(p in merged for p in CAPTCHA_PATTERNS)


def strip_tags(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw or "")).strip()


def extract_note_id(url: str) -> str | None:
    m = NOTE_ID_RE.search(urllib.parse.urlparse(url).path)
    if not m:
        return None
    return m.group(1) or m.group(2)


def extract_profile_uid(url: str) -> str | None:
    m = PROFILE_UID_RE.search(urllib.parse.urlparse(url).path)
    return m.group(1) if m else None


def infer_mode(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    if "/explore/" in path:
        return "note"
    if re.search(r"/user/profile/[^/]+/[0-9a-f]{24,}", path):
        return "note"
    return "profile"


def extract_initial_state(html_text: str) -> str | None:
    marker = "window.__INITIAL_STATE__="
    idx = html_text.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    while start < len(html_text) and html_text[start].isspace():
        start += 1
    if start >= len(html_text) or html_text[start] != "{":
        return None

    depth = 0
    in_str = False
    escaped = False
    for pos in range(start, len(html_text)):
        ch = html_text[pos]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return html_text[start : pos + 1]
    return None


def parse_initial_state(raw: str) -> dict[str, Any]:
    normalized = re.sub(r":\s*undefined\b", ": null", raw)
    normalized = re.sub(r":\s*NaN\b", ": null", normalized)
    return json.loads(normalized)


def parse_profile_cards(html_text: str, max_items: int) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    sections = NOTE_SECTION_RE.findall(html_text)
    for section in sections:
        m_link = re.search(
            r'href="(/user/profile/[^"<>]*/([0-9a-f]{24,})\?[^"<>]*xsec_token=([^"&<>]+)[^"<>]*xsec_source=pc_user)"',
            section,
        )
        if not m_link:
            continue
        rel_url = html.unescape(m_link.group(1))
        note_id = m_link.group(2)
        xsec_token = html.unescape(m_link.group(3))

        m_title = re.search(r'class="title"[^>]*>\s*<span[^>]*>(.*?)</span>', section, re.S)
        title = ""
        if m_title:
            title = html.unescape(strip_tags(m_title.group(1)))
        if not title:
            continue

        cards.append(
            {
                "note_id": note_id,
                "title": title,
                "note_url": f"https://www.xiaohongshu.com{rel_url}",
                "xsec_token": xsec_token,
            }
        )
        if len(cards) >= max_items:
            break
    return cards


def map_comments(raw_comments: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for c in raw_comments[:limit]:
        if not isinstance(c, dict):
            continue
        user = c.get("user_info") or c.get("user") or {}
        comments.append(
            {
                "comment_id": c.get("id") or c.get("comment_id"),
                "content": c.get("content") or "",
                "nickname": user.get("nickname") or user.get("name"),
                "like_count": c.get("liked_count") or c.get("like_count") or 0,
                "time": c.get("create_time") or c.get("createTime"),
            }
        )
    return comments


def resolve_ssl_cafile() -> str | None:
    """Prefer caller-provided SSL_CERT_FILE, otherwise fallback to system cert bundle."""
    env_path = (os.environ.get("SSL_CERT_FILE") or "").strip()
    if env_path:
        return env_path
    for candidate in DEFAULT_CA_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            os.environ["SSL_CERT_FILE"] = str(path)
            return str(path)
    return None


def build_url_opener() -> tuple[Any, str | None]:
    cafile = resolve_ssl_cafile()
    if cafile:
        ssl_context = ssl.create_default_context(cafile=cafile)
    else:
        ssl_context = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
    return opener, cafile


class XhsHttpReader:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.cookie_map = load_xhs_cookies(args.chrome_profile, args.chrome_profile_dir)
        self.cookie_header = cookie_header_from_map(self.cookie_map)
        self.opener, self.ssl_cafile = build_url_opener()
        self.session = self._probe_session()

    def _headers(self, *, accept: str, referer: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": accept,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Cookie": self.cookie_header,
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _open(self, req: urllib.request.Request) -> tuple[str, int, str]:
        timeout = max(3, int(self.args.timeout))
        retries = max(0, int(self.args.retries))
        for attempt in range(retries + 1):
            try:
                with self.opener.open(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    return resp.geturl(), resp.status, body
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if attempt < retries and exc.code >= 500:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                return exc.geturl() if hasattr(exc, "geturl") else req.full_url, exc.code, body
            except urllib.error.URLError:
                if attempt < retries:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                raise
        raise XhsReadError("Unexpected retry loop exit")

    def _json_get(self, url: str, referer: str | None = None) -> tuple[str, int, dict[str, Any]]:
        req = urllib.request.Request(url, headers=self._headers(accept=JSON_ACCEPT, referer=referer))
        final_url, status, body = self._open(req)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"_raw": body[:2000]}
        return final_url, status, data

    def _html_get(self, url: str, referer: str | None = None) -> tuple[str, int, str]:
        req = urllib.request.Request(url, headers=self._headers(accept=HTML_ACCEPT, referer=referer))
        return self._open(req)

    def resolve_url(self, raw_url: str) -> str:
        req = urllib.request.Request(raw_url, headers={"User-Agent": UA})
        final_url, _status, _body = self._open(req)
        return final_url

    def _probe_session(self) -> dict[str, Any]:
        url = "https://edith.xiaohongshu.com/api/sns/web/v2/user/me"
        _final, status, data = self._json_get(url, referer="https://www.xiaohongshu.com/")
        payload = data.get("data") if isinstance(data, dict) else {}
        guest = None
        user_id = None
        if isinstance(payload, dict):
            guest = payload.get("guest")
            user_id = payload.get("user_id") or payload.get("userId") or payload.get("userid")
        return {
            "http_status": status,
            "success": bool(data.get("success")) if isinstance(data, dict) else False,
            "guest": guest,
            "user_id": user_id,
            "ssl_cert_file": self.ssl_cafile,
        }

    def read_profile(self, profile_url: str) -> dict[str, Any]:
        final_url, status, html_text = self._html_get(profile_url, referer="https://www.xiaohongshu.com/")
        blocked = detect_captcha(final_url, html_text)
        cards: list[dict[str, Any]] = []
        if not blocked:
            cards = parse_profile_cards(html_text, max_items=self.args.max_items)

        result: dict[str, Any] = {
            "ok": bool(cards),
            "mode": "profile",
            "resolved_url": final_url,
            "status_code": status,
            "profile_user_id": extract_profile_uid(final_url),
            "cards": cards,
            "session": self.session,
            "fallback": {
                "required": blocked or not cards,
                "reason": (
                    "captcha_or_login_gate"
                    if blocked
                    else "no_profile_cards_from_http"
                    if not cards
                    else ""
                ),
                "next": "use_playwright_profile_snapshot",
            },
        }
        if self.args.debug:
            result["debug"] = {"html_length": len(html_text)}
        return result

    def _extract_note_block(self, state: dict[str, Any], note_id: str | None) -> dict[str, Any] | None:
        note_root = state.get("note") if isinstance(state, dict) else {}
        if not isinstance(note_root, dict):
            return None
        note_map = note_root.get("noteDetailMap")
        if not isinstance(note_map, dict) or not note_map:
            return None
        if note_id and isinstance(note_map.get(note_id), dict):
            return note_map[note_id]
        for val in note_map.values():
            if isinstance(val, dict) and isinstance(val.get("note"), dict):
                return val
        return None

    def _fetch_comments(self, note_id: str, xsec_token: str | None, referer: str) -> dict[str, Any]:
        if not xsec_token:
            return {
                "status": "unavailable",
                "reason": "missing_xsec_token",
                "comments": [],
            }

        token_q = urllib.parse.quote(xsec_token, safe="")
        url = (
            "https://edith.xiaohongshu.com/api/sns/web/v2/comment/page"
            f"?note_id={note_id}&cursor=&top_comment_id=&image_formats=jpg,webp,avif&xsec_token={token_q}"
        )
        _final, http_status, data = self._json_get(url, referer=referer)
        if not isinstance(data, dict):
            return {
                "status": "failed",
                "reason": "non_json_response",
                "http_status": http_status,
                "comments": [],
            }

        if data.get("success"):
            comments_raw = ((data.get("data") or {}).get("comments") or []) if isinstance(data.get("data"), dict) else []
            return {
                "status": "ok",
                "http_status": http_status,
                "count": len(comments_raw),
                "comments": map_comments(comments_raw, self.args.max_comments),
            }

        return {
            "status": "blocked",
            "http_status": http_status,
            "code": data.get("code"),
            "message": data.get("msg") or data.get("message"),
            "comments": [],
        }

    def read_note(self, note_url: str) -> dict[str, Any]:
        final_url, status, html_text = self._html_get(note_url, referer="https://www.xiaohongshu.com/")
        blocked = detect_captcha(final_url, html_text)
        note_id = extract_note_id(final_url) or extract_note_id(note_url)
        xsec_token = urllib.parse.parse_qs(urllib.parse.urlparse(final_url).query).get("xsec_token", [None])[0]

        result: dict[str, Any] = {
            "ok": False,
            "mode": "note",
            "resolved_url": final_url,
            "status_code": status,
            "note_id": note_id,
            "xsec_token": xsec_token,
            "session": self.session,
            "fallback": {"required": False, "reason": "", "next": ""},
        }

        if blocked:
            result["fallback"] = {
                "required": True,
                "reason": "captcha_or_login_gate",
                "next": "use_playwright_note_open",
            }
            return result

        raw_state = extract_initial_state(html_text)
        if not raw_state:
            result["fallback"] = {
                "required": True,
                "reason": "missing_initial_state",
                "next": "use_playwright_note_open",
            }
            if self.args.debug:
                result["debug"] = {"html_length": len(html_text)}
            return result

        try:
            state = parse_initial_state(raw_state)
        except json.JSONDecodeError as exc:
            result["fallback"] = {
                "required": True,
                "reason": f"initial_state_parse_error:{exc}",
                "next": "use_playwright_note_open",
            }
            if self.args.debug:
                result["debug"] = {"initial_state_size": len(raw_state)}
            return result

        note_block = self._extract_note_block(state, note_id)
        if not note_block:
            result["fallback"] = {
                "required": True,
                "reason": "missing_note_block",
                "next": "use_playwright_note_open",
            }
            return result

        note = note_block.get("note") if isinstance(note_block, dict) else {}
        note = note if isinstance(note, dict) else {}
        user = note.get("user") if isinstance(note.get("user"), dict) else {}
        title = (note.get("title") or "").strip()
        desc = (note.get("desc") or "").strip()

        comments_payload = self._fetch_comments(note_id=note_id or "", xsec_token=xsec_token, referer=final_url)
        fallback_required = comments_payload.get("status") in {"blocked", "failed", "unavailable"}
        fallback_reason = ""
        if fallback_required:
            fallback_reason = f"comments_http_{comments_payload.get('status')}"

        result.update(
            {
                "ok": bool(title or desc),
                "title": title,
                "desc": desc,
                "author": {
                    "nickname": user.get("nickname"),
                    "user_id": user.get("user_id") or user.get("id"),
                },
                "comments": comments_payload,
                "fallback": {
                    "required": fallback_required,
                    "reason": fallback_reason,
                    "next": "use_playwright_note_comments" if fallback_required else "",
                },
            }
        )
        return result


def print_or_save(data: dict[str, Any], output: str | None, pretty: bool) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)
    if output:
        out_path = Path(output).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    print(text)


def main() -> int:
    if os.name != "posix" or not (hasattr(os, "uname") and os.uname().sysname == "Darwin"):
        raise XhsReadError("This script currently supports macOS only")

    args = parse_args()
    reader = XhsHttpReader(args)
    resolved = reader.resolve_url(args.url)
    mode = args.mode if args.mode != "auto" else infer_mode(resolved)

    if mode == "profile":
        result = reader.read_profile(resolved)
    else:
        result = reader.read_note(resolved)

    result["input_url"] = args.url
    result["resolved_mode"] = mode
    print_or_save(result, args.output, args.pretty)

    if result.get("fallback", {}).get("required"):
        return 2
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except XhsReadError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
