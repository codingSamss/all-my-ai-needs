#!/usr/bin/env python3
"""Fetch X/Twitter notified timeline (device_follow) with Chrome cookie auth."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import html
import json
import os
import re
import secrets
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT = "https://x.com/i/api/2/notifications/device_follow.json"
DEFAULT_BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
DEFAULT_TIMEOUT_MS = 15000
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_CHROME_PROFILE = "Default"

# If you provide a captured full URL via --request-url, these defaults are ignored.
DEFAULT_QUERY_PARAMS = {
    "count": "20",
    "include_profile_interstitial_type": "1",
    "include_blocking": "1",
    "include_blocked_by": "1",
    "include_followed_by": "1",
    "include_want_retweets": "1",
    "include_mute_edge": "1",
    "include_can_dm": "1",
    "include_can_media_tag": "1",
    "include_ext_has_nft_avatar": "1",
    "include_ext_is_blue_verified": "1",
    "include_ext_verified_type": "1",
    "include_ext_profile_image_shape": "1",
    "include_cards": "1",
    "cards_platform": "Web-12",
    "tweet_mode": "extended",
    "include_entities": "true",
    "include_user_entities": "true",
    "include_ext_alt_text": "true",
    "include_ext_media_color": "true",
    "include_ext_media_availability": "true",
    "include_ext_sensitive_media_warning": "true",
    "include_ext_trusted_friends_metadata": "true",
    "include_quote_count": "true",
    "include_reply_count": "1",
    "simple_quoted_tweet": "true",
    "send_error_codes": "true",
    "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,superFollowMetadata",
}


class DeviceFollowError(RuntimeError):
    """Expected failure for request/auth/parsing issues."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="View X/Twitter notified timeline (device_follow) via Chrome cookies."
    )
    parser.add_argument("--count", type=int, default=20, help="Number of tweets to fetch")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help="HTTP timeout in milliseconds",
    )
    parser.add_argument("--auth-token", help="Twitter auth_token cookie")
    parser.add_argument("--ct0", help="Twitter ct0 cookie")
    parser.add_argument(
        "--chrome-profile",
        default=DEFAULT_CHROME_PROFILE,
        help='Chrome profile name (default: "Default")',
    )
    parser.add_argument(
        "--chrome-profile-dir",
        help="Chrome profile directory or direct Cookies DB path",
    )
    parser.add_argument(
        "--request-url",
        help="Full captured request URL for exact query parameter parity",
    )
    parser.add_argument(
        "--cafile",
        help="Path to a PEM CA bundle used for HTTPS verification",
    )
    parser.add_argument(
        "--capath",
        help="Path to a directory of CA certificates used for HTTPS verification",
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional query parameter override, repeatable",
    )
    parser.add_argument(
        "--bearer-token",
        default=DEFAULT_BEARER_TOKEN,
        help="Bearer token used in Authorization header",
    )
    parser.add_argument(
        "--referer",
        default="https://x.com/i/timeline",
        help="Referer header",
    )
    parser.add_argument("--json", action="store_true", help="Print parsed tweets as JSON")
    parser.add_argument(
        "--json-raw",
        action="store_true",
        help="Print raw API response JSON",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Stable plain output without emoji",
    )
    return parser.parse_args()


def normalize_bearer_token(value: str) -> str:
    token = value.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def parse_param_overrides(raw_pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in raw_pairs:
        if "=" not in pair:
            raise DeviceFollowError(f'Invalid --param "{pair}", expected KEY=VALUE')
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise DeviceFollowError(f'Invalid --param "{pair}", KEY must not be empty')
        out[key] = value
    return out


def build_request_url(args: argparse.Namespace) -> str:
    overrides = parse_param_overrides(args.param)
    if args.request_url:
        parsed = urllib.parse.urlsplit(args.request_url)
        if not parsed.scheme or not parsed.netloc:
            raise DeviceFollowError("Invalid --request-url, expected absolute URL")
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query.update(overrides)
        if args.count > 0:
            query["count"] = str(args.count)
        return urllib.parse.urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urllib.parse.urlencode(query),
                parsed.fragment,
            )
        )

    query = dict(DEFAULT_QUERY_PARAMS)
    query.update(overrides)
    if args.count > 0:
        query["count"] = str(args.count)
    return f"{DEFAULT_ENDPOINT}?{urllib.parse.urlencode(query)}"


def resolve_chrome_cookie_db(profile: str, profile_dir: str | None) -> Path:
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
        raise DeviceFollowError(f"Cannot find Cookies DB under --chrome-profile-dir: {root}")

    base = Path("~/Library/Application Support/Google/Chrome").expanduser()
    db_path = base / profile / "Cookies"
    if db_path.is_file():
        return db_path
    if profile != "Default":
        fallback = base / "Default" / "Cookies"
        if fallback.is_file():
            return fallback
    raise DeviceFollowError(f"Chrome Cookies DB not found: {db_path}")


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
    raise DeviceFollowError("Cannot read Chrome Safe Storage password from Keychain")


def derive_chrome_aes_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def aes_cbc_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    lib_path = ctypes.util.find_library("System")
    if not lib_path:
        raise DeviceFollowError("Cannot load macOS System library for CommonCrypto")
    lib = ctypes.cdll.LoadLibrary(lib_path)
    iv = b" " * 16
    buf = ctypes.create_string_buffer(len(ciphertext) + 16)
    moved = ctypes.c_size_t(0)
    status = lib.CCCrypt(
        1,  # decrypt
        0,  # AES128
        1,  # PKCS7Padding
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
        raise DeviceFollowError(f"CCCrypt decrypt failed, status={status}")
    return buf.raw[: moved.value]


def decrypt_chrome_cookie_value(key: bytes, encrypted_value: bytes) -> str:
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


def extract_twitter_cookies_from_chrome(
    profile: str,
    profile_dir: str | None,
) -> tuple[str | None, str | None]:
    db_path = resolve_chrome_cookie_db(profile, profile_dir)
    password = get_chrome_keychain_password()
    key = derive_chrome_aes_key(password)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        subprocess.run(["cp", str(db_path), tmp_path], check=True, capture_output=True)
        conn = sqlite3.connect(tmp_path)
        rows = conn.execute(
            """
            SELECT host_key, name, value, encrypted_value
            FROM cookies
            WHERE name IN ('auth_token', 'ct0')
              AND (host_key LIKE '%x.com' OR host_key LIKE '%twitter.com')
            """
        ).fetchall()
        conn.close()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not rows:
        return None, None

    picked: dict[str, tuple[int, str]] = {}
    for host, name, value, encrypted in rows:
        cookie_name = str(name)
        if cookie_name not in ("auth_token", "ct0"):
            continue
        domain = str(host or "")
        if domain.endswith("x.com"):
            rank = 0
        elif domain.endswith("twitter.com"):
            rank = 1
        else:
            rank = 2

        plain_value = str(value or "").strip()
        if not plain_value and encrypted:
            try:
                plain_value = decrypt_chrome_cookie_value(key, encrypted)
            except DeviceFollowError:
                continue
        if not plain_value:
            continue

        prev = picked.get(cookie_name)
        if prev is None or rank < prev[0]:
            picked[cookie_name] = (rank, plain_value)

    auth_token = picked.get("auth_token", (9, ""))[1] or None
    ct0 = picked.get("ct0", (9, ""))[1] or None
    return auth_token, ct0


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    auth_token = (args.auth_token or "").strip()
    ct0 = (args.ct0 or "").strip()
    if auth_token and ct0:
        return auth_token, ct0, "cli-args"

    env_auth = (os.getenv("AUTH_TOKEN") or os.getenv("TWITTER_AUTH_TOKEN") or "").strip()
    env_ct0 = (os.getenv("CT0") or os.getenv("TWITTER_CT0") or "").strip()
    if not auth_token and env_auth:
        auth_token = env_auth
    if not ct0 and env_ct0:
        ct0 = env_ct0
    if auth_token and ct0:
        return auth_token, ct0, "env"

    if sys.platform != "darwin":
        raise DeviceFollowError(
            "Missing auth_token/ct0 and Chrome auto extraction only supports macOS"
        )

    chrome_auth, chrome_ct0 = extract_twitter_cookies_from_chrome(
        profile=args.chrome_profile,
        profile_dir=args.chrome_profile_dir,
    )
    if not auth_token and chrome_auth:
        auth_token = chrome_auth
    if not ct0 and chrome_ct0:
        ct0 = chrome_ct0

    if auth_token and ct0:
        return auth_token, ct0, "chrome-cookie"

    raise DeviceFollowError(
        "Unable to resolve auth_token/ct0; provide --auth-token/--ct0 or login x.com in Chrome"
    )


def build_headers(args: argparse.Namespace, auth_token: str, ct0: str) -> dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": normalize_bearer_token(args.bearer_token),
        "content-type": "application/json",
        "cookie": f"auth_token={auth_token}; ct0={ct0}",
        "origin": "https://x.com",
        "referer": args.referer,
        "user-agent": DEFAULT_UA,
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "x-client-uuid": str(uuid.uuid4()),
        "x-twitter-client-deviceid": str(uuid.uuid4()),
        "x-client-transaction-id": secrets.token_hex(16),
    }


def build_opener() -> urllib.request.OpenerDirector:
    return build_opener_with_ssl_context(ssl.create_default_context())


def build_opener_with_ssl_context(ssl_context: ssl.SSLContext) -> urllib.request.OpenerDirector:
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    handlers: list[Any] = [urllib.request.HTTPSHandler(context=ssl_context)]
    if proxy:
        handlers.insert(0, urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def build_ssl_context(args: argparse.Namespace) -> tuple[ssl.SSLContext, str]:
    arg_cafile = (args.cafile or "").strip()
    arg_capath = (args.capath or "").strip()
    if arg_cafile or arg_capath:
        try:
            context = ssl.create_default_context(
                cafile=arg_cafile or None,
                capath=arg_capath or None,
            )
            source = "arg"
            if arg_cafile:
                source += f":--cafile={arg_cafile}"
            elif arg_capath:
                source += f":--capath={arg_capath}"
            return context, source
        except Exception as exc:
            raise DeviceFollowError(f"Invalid CA arguments: {exc}") from exc

    env_cafile = (os.getenv("SSL_CERT_FILE") or "").strip()
    env_capath = (os.getenv("SSL_CERT_DIR") or "").strip()
    if env_cafile or env_capath:
        try:
            context = ssl.create_default_context(
                cafile=env_cafile or None,
                capath=env_capath or None,
            )
            source = "env"
            if env_cafile:
                source += f":SSL_CERT_FILE={env_cafile}"
            elif env_capath:
                source += f":SSL_CERT_DIR={env_capath}"
            return context, source
        except Exception as exc:
            print(f"[warn] invalid SSL cert env, fallback to next trust source: {exc}", file=sys.stderr)

    try:
        import certifi  # type: ignore

        cafile = certifi.where()
        if cafile and Path(cafile).is_file():
            return ssl.create_default_context(cafile=cafile), f"certifi:{cafile}"
    except Exception:
        pass

    return ssl.create_default_context(), "system-default"


def allow_insecure_ssl_retry() -> bool:
    value = (os.getenv("BIRD_INSECURE_SSL") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_ssl_cert_verify_error(exc: urllib.error.URLError) -> bool:
    text = f"{exc} {getattr(exc, 'reason', '')}".upper()
    return "CERTIFICATE_VERIFY_FAILED" in text


def build_ssl_troubleshooting_hint(args: argparse.Namespace) -> str:
    if args.cafile or args.capath:
        return "Check the provided CA path and your proxy certificate chain."

    try:
        import certifi  # type: ignore

        cafile = certifi.where()
        if cafile and Path(cafile).is_file():
            return (
                f'Try rerunning with --cafile "{cafile}" '
                "or set SSL_CERT_FILE to the same path."
            )
    except Exception:
        pass

    return "Try rerunning with --cafile /path/to/cacert.pem or set SSL_CERT_FILE."


def open_request(
    req: urllib.request.Request,
    timeout_s: float,
    ssl_context: ssl.SSLContext,
) -> str:
    opener = build_opener_with_ssl_context(ssl_context)
    with opener.open(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(
    url: str,
    headers: dict[str, str],
    timeout_ms: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    timeout_s = max(1, timeout_ms / 1000)
    ssl_context, ssl_source = build_ssl_context(args)
    if ssl_source != "system-default":
        print(f"[info] SSL trust source: {ssl_source}", file=sys.stderr)
    try:
        body = open_request(req, timeout_s=timeout_s, ssl_context=ssl_context)
    except urllib.error.HTTPError as exc:
        snippet = ""
        try:
            snippet = exc.read(300).decode("utf-8", errors="replace")
        except Exception:
            pass
        raise DeviceFollowError(f"HTTP {exc.code} from device_follow: {snippet}") from exc
    except urllib.error.URLError as exc:
        if is_ssl_cert_verify_error(exc) and allow_insecure_ssl_retry():
            print(
                "[warn] SSL verification failed; retrying with insecure SSL because "
                "BIRD_INSECURE_SSL is enabled.",
                file=sys.stderr,
            )
            insecure_context = ssl._create_unverified_context()
            try:
                body = open_request(req, timeout_s=timeout_s, ssl_context=insecure_context)
            except urllib.error.HTTPError as insecure_http_exc:
                snippet = ""
                try:
                    snippet = insecure_http_exc.read(300).decode("utf-8", errors="replace")
                except Exception:
                    pass
                raise DeviceFollowError(
                    f"HTTP {insecure_http_exc.code} from device_follow: {snippet}"
                ) from insecure_http_exc
            except urllib.error.URLError as insecure_exc:
                raise DeviceFollowError(
                    f"Network error while calling device_follow: {insecure_exc}"
                ) from insecure_exc
        else:
            if is_ssl_cert_verify_error(exc):
                hint = build_ssl_troubleshooting_hint(args)
                raise DeviceFollowError(
                    f"SSL certificate verification failed while calling device_follow: {exc}. "
                    f"{hint}"
                ) from exc
            raise DeviceFollowError(f"Network error while calling device_follow: {exc}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DeviceFollowError(f"Invalid JSON response: {exc}") from exc
    if not isinstance(payload, dict):
        raise DeviceFollowError("Unexpected response payload type")
    return payload


def pick_media_urls(tweet: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    entities = tweet.get("extended_entities") or tweet.get("entities") or {}
    media_items = entities.get("media") or []
    if not isinstance(media_items, list):
        return out
    for item in media_items:
        if not isinstance(item, dict):
            continue
        mtype = str(item.get("type") or "").strip() or "media"
        if mtype in ("video", "animated_gif"):
            variants = (
                item.get("video_info", {}).get("variants", [])
                if isinstance(item.get("video_info"), dict)
                else []
            )
            best_url = ""
            best_bitrate = -1
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                if variant.get("content_type") != "video/mp4":
                    continue
                url = str(variant.get("url") or "").strip()
                bitrate = int(variant.get("bitrate") or 0)
                if not url:
                    continue
                if bitrate > best_bitrate:
                    best_bitrate = bitrate
                    best_url = url
            if best_url:
                out.append((mtype, best_url))
                continue
        media_url = str(item.get("media_url_https") or item.get("media_url") or "").strip()
        if media_url:
            out.append((mtype, media_url))
    return out


def normalize_text(tweet: dict[str, Any]) -> str:
    text = str(tweet.get("full_text") or tweet.get("text") or "").strip()
    return html.unescape(text)


def extract_tweet_id_from_entry(entry: dict[str, Any]) -> str | None:
    entry_id = str(entry.get("entryId") or entry.get("entry_id") or "")
    match = re.search(r"(?:tweet-|sq-I-t-)(\d+)", entry_id)
    if match:
        return match.group(1)

    paths = [
        ("content", "item", "content", "tweet", "id"),
        ("content", "itemContent", "tweet", "id"),
        ("content", "itemContent", "tweet_results", "result", "rest_id"),
    ]
    for path in paths:
        cur: Any = entry
        valid = True
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                valid = False
                break
            cur = cur[key]
        if valid and isinstance(cur, (str, int)):
            tweet_id = str(cur).strip()
            if tweet_id.isdigit():
                return tweet_id
    return None


def collect_ordered_tweet_ids(payload: dict[str, Any], tweets: dict[str, Any]) -> list[str]:
    instructions = payload.get("timeline", {}).get("instructions", [])
    ranked: list[tuple[int, str]] = []
    if isinstance(instructions, list):
        for instruction in instructions:
            if not isinstance(instruction, dict):
                continue
            entries = None
            if isinstance(instruction.get("addEntries"), dict):
                entries = instruction["addEntries"].get("entries")
            if entries is None:
                entries = instruction.get("entries")
            if not isinstance(entries, list):
                continue

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                tweet_id = extract_tweet_id_from_entry(entry)
                if not tweet_id or tweet_id not in tweets:
                    continue
                sort_index = entry.get("sortIndex")
                rank = int(sort_index) if isinstance(sort_index, str) and sort_index.isdigit() else 0
                ranked.append((rank, tweet_id))

    if ranked:
        ranked.sort(key=lambda x: x[0], reverse=True)
        out: list[str] = []
        seen: set[str] = set()
        for _, tweet_id in ranked:
            if tweet_id in seen:
                continue
            seen.add(tweet_id)
            out.append(tweet_id)
        return out

    # Fallback: sort by tweet id descending if timeline entries are missing.
    return sorted(tweets.keys(), key=lambda x: int(x), reverse=True)


def parse_device_follow_payload(payload: dict[str, Any], count: int) -> list[dict[str, Any]]:
    global_objects = payload.get("globalObjects") or {}
    users = global_objects.get("users") or {}
    tweets = global_objects.get("tweets") or {}
    if not isinstance(users, dict) or not isinstance(tweets, dict):
        raise DeviceFollowError("Unexpected response structure: missing globalObjects.users/tweets")

    ordered_ids = collect_ordered_tweet_ids(payload, tweets)
    result: list[dict[str, Any]] = []
    for tweet_id in ordered_ids:
        raw = tweets.get(tweet_id)
        if not isinstance(raw, dict):
            continue
        user_id = str(raw.get("user_id_str") or raw.get("user_id") or "").strip()
        user_obj = users.get(user_id, {}) if user_id else {}
        if not isinstance(user_obj, dict):
            user_obj = {}

        username = str(user_obj.get("screen_name") or "").strip() or "unknown"
        name = str(user_obj.get("name") or "").strip() or username
        created_at = str(raw.get("created_at") or "").strip()
        tweet_url = f"https://x.com/{username}/status/{tweet_id}"

        media = pick_media_urls(raw)
        result.append(
            {
                "id": tweet_id,
                "author": {"username": username, "name": name},
                "text": normalize_text(raw),
                "created_at": created_at,
                "like_count": int(raw.get("favorite_count") or 0),
                "retweet_count": int(raw.get("retweet_count") or 0),
                "reply_count": int(raw.get("reply_count") or 0),
                "url": tweet_url,
                "media": [{"type": mtype, "url": murl} for mtype, murl in media],
            }
        )
        if len(result) >= count:
            break
    return result


def format_media_label(media_type: str, plain: bool) -> str:
    if plain:
        if media_type == "video":
            return "VIDEO"
        if media_type == "animated_gif":
            return "GIF"
        return "PHOTO"
    if media_type == "video":
        return "VIDEO"
    if media_type == "animated_gif":
        return "GIF"
    return "PHOTO"


def print_tweets(tweets: list[dict[str, Any]], plain: bool) -> None:
    if not tweets:
        print("No tweets found in device_follow timeline.")
        return

    for tweet in tweets:
        author = tweet["author"]
        print(f"\n@{author['username']} ({author['name']}):")
        print(tweet["text"])
        for media in tweet.get("media", []):
            print(f"{format_media_label(media['type'], plain)}: {media['url']}")
        if tweet.get("created_at"):
            print(f"date: {tweet['created_at']}")
        print(
            "likes: {likes}  retweets: {retweets}  replies: {replies}".format(
                likes=tweet.get("like_count", 0),
                retweets=tweet.get("retweet_count", 0),
                replies=tweet.get("reply_count", 0),
            )
        )
        print(f"url: {tweet['url']}")
        print("-" * 50)


def maybe_warn_default_query(request_url: str, used_custom_url: bool) -> None:
    if used_custom_url:
        return
    parsed = urllib.parse.urlsplit(request_url)
    param_count = len(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    print(
        f"[warn] using built-in query params ({param_count} keys). "
        "Use --request-url with captured full URL for exact parity.",
        file=sys.stderr,
    )


def validate_args(args: argparse.Namespace) -> None:
    if args.count <= 0:
        raise DeviceFollowError("--count must be a positive integer")
    if args.timeout_ms <= 0:
        raise DeviceFollowError("--timeout-ms must be a positive integer")
    if args.cafile and not Path(args.cafile).is_file():
        raise DeviceFollowError(f"--cafile does not exist or is not a file: {args.cafile}")
    if args.capath and not Path(args.capath).is_dir():
        raise DeviceFollowError(f"--capath does not exist or is not a directory: {args.capath}")


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        auth_token, ct0, source = resolve_credentials(args)
        request_url = build_request_url(args)
        maybe_warn_default_query(request_url, used_custom_url=bool(args.request_url))
        print(f"[info] credentials source: {source}", file=sys.stderr)
        headers = build_headers(args, auth_token=auth_token, ct0=ct0)
        payload = fetch_json(request_url, headers=headers, timeout_ms=args.timeout_ms, args=args)
        tweets = parse_device_follow_payload(payload, count=args.count)

        if args.json_raw:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.json:
            print(json.dumps(tweets, ensure_ascii=False, indent=2))
        else:
            print_tweets(tweets, plain=args.plain)
        return 0
    except DeviceFollowError as exc:
        print(f"[err] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
