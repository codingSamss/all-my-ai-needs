#!/usr/bin/env python3
"""Export Xiaohongshu-related Chrome cookies to Playwright JSON format (macOS)."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class CookieExportError(RuntimeError):
    """Raised when cookie export fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Xiaohongshu Chrome cookies as Playwright addCookies JSON."
    )
    parser.add_argument(
        "--out",
        default="/tmp/xhs_cookies_playwright.json",
        help="Output JSON path. Default: /tmp/xhs_cookies_playwright.json",
    )
    parser.add_argument(
        "--chrome-profile",
        default="Default",
        help='Chrome profile name. Default: "Default"',
    )
    parser.add_argument(
        "--chrome-profile-dir",
        help="Chrome profile root dir or direct Cookies DB path.",
    )
    parser.add_argument(
        "--domains",
        default="xiaohongshu.com,xhslink.com",
        help="Comma-separated domain filters. Default: xiaohongshu.com,xhslink.com",
    )
    parser.add_argument(
        "--min-required",
        type=int,
        default=1,
        help="Minimum cookie count required for success. Default: 1",
    )
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
        raise CookieExportError(f"Cannot find Cookies DB under: {root}")

    base = Path("~/Library/Application Support/Google/Chrome").expanduser()
    db_path = base / profile / "Cookies"
    if db_path.is_file():
        return db_path
    if profile != "Default":
        fallback = base / "Default" / "Cookies"
        if fallback.is_file():
            return fallback
    raise CookieExportError(f"Chrome Cookies DB not found: {db_path}")


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
    raise CookieExportError("Cannot read Chrome Safe Storage password from Keychain")


def derive_chrome_aes_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def aes_cbc_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    lib_path = ctypes.util.find_library("System")
    if not lib_path:
        raise CookieExportError("Cannot load macOS System library for CommonCrypto")
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
        raise CookieExportError(f"CCCrypt decrypt failed, status={status}")
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


def chrome_time_to_unix(expires_utc: int) -> int:
    if not expires_utc or expires_utc <= 0:
        return -1
    unix_s = int(expires_utc / 1_000_000 - 11_644_473_600)
    return unix_s if unix_s > 0 else -1


def map_same_site(raw: int | None) -> str | None:
    if raw is None:
        return None
    mapping = {
        0: "None",
        1: "Lax",
        2: "Strict",
    }
    return mapping.get(int(raw))


def read_cookie_rows(db_path: Path, domains: list[str]) -> list[sqlite3.Row]:
    clauses = []
    params: list[Any] = []
    for domain in domains:
        d = domain.strip().lstrip(".")
        if not d:
            continue
        clauses.append("host_key LIKE ?")
        params.append(f"%{d}")
    if not clauses:
        raise CookieExportError("No valid domains to query")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        subprocess.run(["cp", str(db_path), tmp_path], check=True, capture_output=True)
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        where_sql = " OR ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT host_key, name, value, encrypted_value, path, expires_utc,
                   is_secure, is_httponly, samesite, last_access_utc
            FROM cookies
            WHERE ({where_sql})
            ORDER BY host_key, name, last_access_utc DESC
            """,
            params,
        ).fetchall()
        conn.close()
        return rows
    except subprocess.CalledProcessError as exc:
        raise CookieExportError(f"Failed to copy cookie DB: {exc}") from exc
    except sqlite3.Error as exc:
        raise CookieExportError(f"Failed to read cookie DB: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def to_playwright_cookies(rows: list[sqlite3.Row], key: bytes) -> list[dict[str, Any]]:
    picked: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        domain = str(row["host_key"] or "").strip()
        name = str(row["name"] or "").strip()
        path = str(row["path"] or "/").strip() or "/"
        if not domain or not name:
            continue

        try:
            value = decrypt_cookie_value(
                key=key,
                plain_value=str(row["value"] or ""),
                encrypted_value=row["encrypted_value"] or b"",
            )
        except CookieExportError:
            continue

        if not value:
            continue

        cookie: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "expires": chrome_time_to_unix(int(row["expires_utc"] or 0)),
            "httpOnly": bool(row["is_httponly"]),
            "secure": bool(row["is_secure"]),
        }
        same_site = map_same_site(row["samesite"])
        if same_site:
            cookie["sameSite"] = same_site

        dedup_key = (domain, path, name)
        prev = picked.get(dedup_key)
        if not prev:
            picked[dedup_key] = cookie
            continue
        if int(cookie["expires"]) > int(prev.get("expires", -1)):
            picked[dedup_key] = cookie

    return list(picked.values())


def write_output(path: Path, cookies: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize(cookies: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in cookies:
        domain = str(c.get("domain", ""))
        counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[0]))


def main() -> int:
    if os.name != "posix" or not (hasattr(os, "uname") and os.uname().sysname == "Darwin"):
        raise CookieExportError("This script currently supports macOS only")

    args = parse_args()
    domains = [x.strip() for x in args.domains.split(",") if x.strip()]
    db_path = resolve_cookie_db(args.chrome_profile, args.chrome_profile_dir)
    key = derive_chrome_aes_key(get_chrome_keychain_password())
    rows = read_cookie_rows(db_path, domains)
    cookies = to_playwright_cookies(rows, key)

    if len(cookies) < max(0, args.min_required):
        raise CookieExportError(
            f"Exported cookies={len(cookies)}, below --min-required={args.min_required}. "
            "Please ensure Chrome is logged in and cookies are available."
        )

    out_path = Path(args.out).expanduser()
    write_output(out_path, cookies)
    by_domain = summarize(cookies)
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(out_path),
                "cookie_count": len(cookies),
                "domain_counts": by_domain,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CookieExportError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
