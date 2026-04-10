#!/usr/bin/env python3
"""LINUX DO read-only helper via Discourse JSON API + Chrome Cookie auth (macOS)."""
from __future__ import annotations

import argparse, ctypes, ctypes.util, hashlib, html, json, os, re
import sqlite3, subprocess, sys, tempfile, urllib.error, urllib.parse, urllib.request

BASE_URL = "https://linux.do"
DEFAULT_TIMEOUT = 20
_CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_UA_TEMPLATE = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver} Safari/537.36"
)
_DEFAULT_CHROME_VER = "130.0.0.0"


def _detect_chrome_ua() -> str:
    """Build a User-Agent matching the local Chrome version for cf_clearance."""
    try:
        r = subprocess.run([_CHROME_APP, "--version"], capture_output=True, text=True, check=True)
        full_ver = r.stdout.strip().split()[-1]  # e.g. "144.0.7559.133"
        major = full_ver.split(".")[0]
        return _UA_TEMPLATE.format(ver=f"{major}.0.0.0")
    except Exception:
        return _UA_TEMPLATE.format(ver=_DEFAULT_CHROME_VER)


DEFAULT_UA: str = ""  # resolved lazily
KNOWN_CATEGORIES = [
    ("develop", 4, "开发调优"), ("domestic", 98, "国产替代"),
    ("resource", 14, "资源荟萃"), ("wiki", 42, "文档共建"),
    ("job", 27, "非我莫属"), ("reading", 32, "读书成诗"),
    ("news", 34, "前沿快讯"), ("feeds", 92, "网络记忆"),
    ("welfare", 36, "福利羊毛"), ("gossip", 11, "搞七捻三"),
    ("square", 110, "虫洞广场"), ("feedback", 2, "运营反馈"),
]
COOKIE_STRING: str | None = None

# -- Chrome Cookie extraction (macOS) --

CHROME_COOKIES_DB = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Cookies"
)

class CookieError(RuntimeError):
    """Non-fatal: Chrome cookie extraction failed."""

class FetchError(RuntimeError):
    """Raised when HTTP fetch fails."""

def _get_chrome_keychain_password() -> bytes:
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "Chrome Safe Storage", "-w"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip().encode("utf-8")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise CookieError(f"无法从 Keychain 获取 Chrome Safe Storage 密码: {exc}") from exc

def _derive_aes_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)

def _aes_cbc_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    lib_path = ctypes.util.find_library("System")
    if not lib_path:
        raise CookieError("无法加载 macOS System 库 (CommonCrypto)")
    lib = ctypes.cdll.LoadLibrary(lib_path)
    iv = b" " * 16  # 16 bytes of 0x20
    buf = ctypes.create_string_buffer(len(ciphertext) + 16)
    moved = ctypes.c_size_t(0)
    # CCCrypt: op=Decrypt(1), alg=AES128(0), opts=PKCS7(1)
    status = lib.CCCrypt(1, 0, 1, key, len(key), iv,
                         ciphertext, len(ciphertext), buf, len(ciphertext) + 16, ctypes.byref(moved))
    if status != 0:
        raise CookieError(f"CCCrypt 解密失败, status={status}")
    return buf.raw[:moved.value]

def extract_chrome_cookies(domain: str = "linux.do") -> str:
    if not os.path.isfile(CHROME_COOKIES_DB):
        raise CookieError(f"Chrome Cookies 数据库不存在: {CHROME_COOKIES_DB}")
    password = _get_chrome_keychain_password()
    key = _derive_aes_key(password)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        subprocess.run(["cp", CHROME_COOKIES_DB, tmp_path], check=True, capture_output=True)
        conn = sqlite3.connect(tmp_path)
        rows = conn.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?",
            (f"%{domain}%",),
        ).fetchall()
        conn.close()
    finally:
        os.unlink(tmp_path)
    if not rows:
        raise CookieError(f"Chrome Cookies 中未找到 {domain} 的 cookie")
    pairs: list[str] = []
    for name, enc in rows:
        if not enc:
            continue
        try:
            if enc[:3] == b"v10":
                raw = _aes_cbc_decrypt(key, enc[3:])
                # Chrome v10 on macOS: 32-byte header (nonce/hash) before actual value
                val = raw[32:].decode("utf-8", errors="replace") if len(raw) > 32 else ""
            else:
                val = enc.decode("utf-8", errors="replace")
            if not val:
                continue
            pairs.append(f"{name}={val}")
        except CookieError:
            continue
    if not pairs:
        raise CookieError(f"Chrome Cookies 中 {domain} 的 cookie 均解密失败")
    return "; ".join(pairs)

# -- Cookie resolution --

def _load_cookie_from_file(path: str) -> str:
    try:
        content = open(path, "r", encoding="utf-8").read()
    except OSError as exc:
        raise FetchError(f"读取 cookie 文件失败: {path}\n{exc}") from exc
    if not content.strip():
        raise FetchError(f"cookie 文件为空: {path}")
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    pairs: list[str] = []
    for line in lines:
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            if parts[5].strip():
                pairs.append(f"{parts[5].strip()}={parts[6].strip()}")
    if pairs:
        return "; ".join(pairs)
    raw = " ".join(lines).strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    if "=" not in raw:
        raise FetchError(f"cookie 文件内容格式不合法: {path}")
    return raw

def resolve_cookie(args: argparse.Namespace) -> None:
    global COOKIE_STRING
    if getattr(args, "cookie", None):
        COOKIE_STRING = args.cookie; return
    cookie_file = getattr(args, "cookie_file", None)
    if cookie_file:
        COOKIE_STRING = _load_cookie_from_file(cookie_file); return
    env_cookie = os.getenv("LINUXDO_COOKIE")
    if env_cookie:
        COOKIE_STRING = env_cookie; return
    if sys.platform == "darwin":
        try:
            COOKIE_STRING = extract_chrome_cookies(); return
        except CookieError as exc:
            print(f"[WARN] Chrome cookie 自动提取失败: {exc}", file=sys.stderr)
    COOKIE_STRING = None

# -- HTTP helpers --

def _which(binary: str) -> str | None:
    for p in os.getenv("PATH", "").split(os.pathsep):
        c = os.path.join(p, binary)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None

def _get_ua() -> str:
    global DEFAULT_UA
    if not DEFAULT_UA:
        DEFAULT_UA = os.getenv("LINUXDO_UA") or _detect_chrome_ua()
    return DEFAULT_UA

def _headers() -> dict[str, str]:
    h = {"User-Agent": _get_ua(), "Accept": "application/json"}
    if COOKIE_STRING:
        h["Cookie"] = COOKIE_STRING
    return h

def is_cloudflare_challenge(text: str) -> bool:
    return any(s in text for s in (
        "__cf_chl_opt", "__CF$cv$params", "Just a moment...",
        "Enable JavaScript and cookies to continue"))

def _fetch_urllib(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers=_headers())
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})) if proxy else urllib.request.build_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try: body = exc.read(400).decode("utf-8", errors="replace")
        except Exception: pass
        raise FetchError(f"HTTP {exc.code}: {url}\n{body.strip()}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"网络请求失败: {url}\n{exc}") from exc

def _fetch_curl(url: str, timeout: int) -> str:
    if not _which("curl"):
        raise FetchError("本机未检测到 curl")
    cmd = ["curl", "-sS", "--fail", "--max-time", str(timeout), "-L",
           "-A", _get_ua()]
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy:
        cmd.extend(["--proxy", proxy])
    for k, v in _headers().items():
        if k.lower() != "user-agent":
            cmd.extend(["-H", f"{k}: {v}"])
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise FetchError(f"curl 失败: {url}\n{proc.stderr.decode('utf-8', errors='replace').strip()}")
    return proc.stdout.decode("utf-8", errors="replace")

def fetch_text(url: str, timeout: int) -> str:
    first_err = ""
    try:
        text = _fetch_urllib(url, timeout=timeout)
        if not is_cloudflare_challenge(text):
            return text
        first_err = "urllib 命中 Cloudflare challenge"
    except (FetchError, UnicodeEncodeError) as exc:
        first_err = str(exc)
    try:
        text = _fetch_curl(url, timeout=timeout)
        if not is_cloudflare_challenge(text):
            return text
        raise FetchError("curl 也命中 Cloudflare challenge")
    except FetchError as exc:
        raise FetchError(
            f"请求失败（urllib + curl）。\nurllib: {first_err}\ncurl: {exc}\n"
            "建议：配置代理或设置 Cookie 后重试。") from exc

def fetch_json(url: str, timeout: int) -> dict | list:
    text = fetch_text(url, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"JSON 解析失败: {url}\n{exc}\n{text[:300]}") from exc

# -- Output formatting --

def strip_html(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()

def truncate(raw: str, mx: int) -> str:
    t = raw.strip()
    return t if len(t) <= mx else t[:mx - 1].rstrip() + "..."

def _cat_name(cat_id: int) -> str:
    for _, cid, name in KNOWN_CATEGORIES:
        if cid == cat_id:
            return name
    return ""

def _format_topic(t: dict, chars: int) -> str:
    tid = t.get("id", "-")
    title = t.get("title") or t.get("fancy_title") or ""
    cat = _cat_name(t.get("category_id", 0))
    views = t.get("views", 0)
    replies = t.get("posts_count", 1) - 1
    excerpt = strip_html(t.get("excerpt", ""))
    poster = ""
    for p in (t.get("posters") or [])[:1]:
        for u in t.get("_users", []):
            if u.get("id") == p.get("user_id"):
                poster = u.get("username", ""); break
    lines = [f"[{tid}] {title}"]
    meta = []
    if cat: meta.append(f"分类: {cat}")
    if poster: meta.append(f"作者: {poster}")
    meta += [f"回复: {replies}", f"浏览: {views}"]
    lines.append("  " + " | ".join(meta))
    if excerpt:
        lines.append(f"  摘要: {truncate(excerpt, chars)}")
    lines.append(f"  链接: {BASE_URL}/t/{tid}")
    return "\n".join(lines)

# -- Commands --

def cmd_whoami(args: argparse.Namespace) -> int:
    data = fetch_json(f"{BASE_URL}/session/current.json", timeout=args.timeout)
    user = data.get("current_user") or {}
    if not user:
        print("未登录（cookie 无效或已过期）。"); return 1
    print(f"用户名: {user.get('username', '-')}")
    print(f"  昵称: {user.get('name', '-')}")
    print(f"  信任等级: {user.get('trust_level', '-')}")
    print(f"  未读通知: {user.get('unread_notifications', 0)}")
    print(f"  链接: {BASE_URL}/u/{user.get('username', '')}")
    return 0

def _print_topics(data: dict, limit: int, chars: int) -> int:
    topics = (data.get("topic_list") or {}).get("topics") or []
    users = data.get("users") or []
    if not topics:
        print("未获取到帖子。"); return 0
    for t in topics[:limit]:
        t["_users"] = users
        print(_format_topic(t, chars=chars)); print()
    return 0

def cmd_latest(args: argparse.Namespace) -> int:
    return _print_topics(
        fetch_json(f"{BASE_URL}/latest.json?page={args.page}", timeout=args.timeout),
        args.limit, args.chars)

def cmd_top(args: argparse.Namespace) -> int:
    data = fetch_json(f"{BASE_URL}/top.json?period={args.period}", timeout=args.timeout)
    topics = (data.get("topic_list") or {}).get("topics") or []
    if not topics:
        print(f"未获取到 {args.period} 热门帖子。"); return 0
    users = data.get("users") or []
    for t in topics[:args.limit]:
        t["_users"] = users
        print(_format_topic(t, chars=args.chars)); print()
    return 0

def cmd_search(args: argparse.Namespace) -> int:
    query = args.query.strip()
    if not query:
        raise FetchError("搜索关键词不能为空。")
    url = f"{BASE_URL}/search.json?q={urllib.parse.quote(query, safe='')}"
    data = fetch_json(url, timeout=args.timeout)
    topics = data.get("topics") or []
    posts = data.get("posts") or []
    if not topics and not posts:
        print(f"未找到与「{query}」相关的结果。"); return 0
    if topics:
        print(f"=== 相关主题 ({len(topics)}) ===")
        for t in topics[:args.limit]:
            tid = t.get("id", "-")
            title = t.get("title") or ""
            cat = _cat_name(t.get("category_id", 0))
            meta = []
            if cat: meta.append(f"分类: {cat}")
            meta += [f"回复: {t.get('posts_count', 1) - 1}", f"浏览: {t.get('views', 0)}"]
            print(f"[{tid}] {title}")
            print("  " + " | ".join(meta))
            print(f"  链接: {BASE_URL}/t/{tid}\n")
    if posts:
        print(f"=== 匹配回帖 ({len(posts)}) ===")
        for p in posts[:args.limit]:
            tid = p.get("topic_id", "-")
            print(f"[topic:{tid}] @{p.get('username', '-')}")
            blurb = strip_html(p.get("blurb", ""))
            if blurb:
                print(f"  内容: {truncate(blurb, args.chars)}")
            print(f"  链接: {BASE_URL}/t/{tid}/{p.get('post_number', 1)}\n")
    return 0

def _parse_topic_ref(ref: str) -> int:
    ref = ref.strip()
    m = re.search(r"/t/[^/]+/(\d+)", ref)
    if m: return int(m.group(1))
    m = re.fullmatch(r"[^/]+/(\d+)", ref)
    if m: return int(m.group(1))
    if ref.isdigit(): return int(ref)
    raise FetchError("无法解析 topic 参数。支持: URL / slug/id / id")

def _fetch_topic_json(topic_id: int, timeout: int, post_number: int | None = None) -> dict:
    """
    Some Cloudflare rules block `/t/<id>.json` and `/posts.json`.
    Prefer `/t/topic/<id>.json` and use `post_number` for pagination.
    """
    urls: list[str] = []
    if post_number and post_number > 0:
        urls.extend([
            f"{BASE_URL}/t/topic/{topic_id}.json?post_number={post_number}",
            f"{BASE_URL}/t/{topic_id}.json?post_number={post_number}",
        ])
    urls.extend([
        f"{BASE_URL}/t/topic/{topic_id}.json",
        f"{BASE_URL}/t/{topic_id}.json",
    ])

    last_err: FetchError | None = None
    for url in urls:
        try:
            data = fetch_json(url, timeout=timeout)
            if isinstance(data, dict):
                return data
            raise FetchError(f"topic 接口返回异常结构: {url}")
        except FetchError as exc:
            last_err = exc
            continue
    assert last_err is not None
    raise last_err

def cmd_topic(args: argparse.Namespace) -> int:
    topic_id = _parse_topic_ref(args.topic)
    data = _fetch_topic_json(topic_id, timeout=args.timeout)
    title = data.get("title") or data.get("fancy_title") or ""
    cat = _cat_name(data.get("category_id", 0))
    meta = []
    if cat: meta.append(f"分类: {cat}")
    meta += [f"回复: {data.get('reply_count', 0)}", f"浏览: {data.get('views', 0)}",
             f"赞: {data.get('like_count', 0)}", f"创建: {data.get('created_at', '-')}"]
    print(f"主题: {title}")
    print("  " + " | ".join(meta))
    print(f"  链接: {BASE_URL}/t/{topic_id}\n")
    ps = data.get("post_stream") or {}
    posts = ps.get("posts") or []
    if args.page > 0:
        start_post_no = args.page * 20 + 1
        extra = _fetch_topic_json(topic_id, timeout=args.timeout, post_number=start_post_no)
        raw_posts = extra.get("post_stream", {}).get("posts") or []
        end_post_no = start_post_no + 19
        page_posts = [
            p for p in raw_posts
            if start_post_no <= int(p.get("post_number", 0)) <= end_post_no
        ]
        posts = page_posts or raw_posts
    if not posts:
        print("未获取到楼层内容。"); return 0
    for idx, p in enumerate(posts[:args.posts], start=1):
        likes = 0
        for a in (p.get("actions_summary") or []):
            if a.get("id") == 2: likes = a.get("count", 0); break
        content = strip_html(p.get("cooked", ""))
        print(f"[#{p.get('post_number', idx)}] @{p.get('username', '-')} | "
              f"时间: {p.get('created_at', '-')} | 赞: {likes}")
        if content:
            print(f"  {truncate(content, args.chars)}")
        print()
    return 0

def cmd_category(args: argparse.Namespace) -> int:
    if not args.category:
        try:
            data = fetch_json(f"{BASE_URL}/categories.json", timeout=args.timeout)
            cats = (data.get("category_list") or {}).get("categories") or []
        except FetchError:
            cats = []
        if cats:
            for c in sorted(cats, key=lambda c: c.get("topic_count", 0), reverse=True):
                desc = strip_html(c.get("description_text", "") or c.get("description", ""))
                print(f"[{c.get('id', '-')}] {c.get('name', '')} ({c.get('slug', '')}) | "
                      f"帖子数: {c.get('topic_count', 0)}")
                if desc: print(f"  简介: {truncate(desc, args.chars)}")
        else:
            for slug, cid, name in KNOWN_CATEGORIES:
                print(f"[{cid}] {name} ({slug})")
        return 0
    ref = args.category.strip()
    slug, cid, display = ref, None, ref
    for s, c, n in KNOWN_CATEGORIES:
        if ref == s or (ref.isdigit() and int(ref) == c):
            slug, cid, display = s, c, f"{n} ({s})"; break
    path = f"/c/{slug}/{cid}/l/latest.json" if cid else f"/c/{slug}/l/latest.json"
    data = fetch_json(f"{BASE_URL}{path}?page={args.page}", timeout=args.timeout)
    print(f"分类: {display}")
    print(f"链接: {BASE_URL}/c/{slug}" + (f"/{cid}" if cid else "") + "\n")
    return _print_topics(data, args.limit, args.chars)

# -- argparse --

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="linuxdo.py",
        description="LINUX DO read-only helper (Discourse JSON API + Chrome Cookie auth).")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--cookie", default=None, help="Cookie 字符串")
    p.add_argument("--cookie-file", default=os.getenv("LINUXDO_COOKIE_FILE"),
                   help="Cookie 文件路径")
    sub = p.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("whoami", help="查看当前登录身份").set_defaults(func=cmd_whoami)

    s = sub.add_parser("latest", help="最新帖子")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--page", type=int, default=0)
    s.add_argument("--chars", type=int, default=140)
    s.set_defaults(func=cmd_latest)

    s = sub.add_parser("top", help="热门帖子")
    s.add_argument("--period", default="weekly",
                   choices=["daily", "weekly", "monthly", "yearly", "all"])
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--chars", type=int, default=140)
    s.set_defaults(func=cmd_top)

    s = sub.add_parser("search", help="全文搜索")
    s.add_argument("query", help="搜索关键词")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--chars", type=int, default=140)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("topic", help="帖子详情")
    s.add_argument("topic", help="URL / slug/id / id")
    s.add_argument("--posts", type=int, default=5)
    s.add_argument("--chars", type=int, default=300)
    s.add_argument("--page", type=int, default=0)
    s.set_defaults(func=cmd_topic)

    s = sub.add_parser("category", help="分类列表或分类帖子")
    s.add_argument("category", nargs="?")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--page", type=int, default=0)
    s.add_argument("--chars", type=int, default=140)
    s.set_defaults(func=cmd_category)

    return p

def main() -> int:
    args = build_parser().parse_args()
    try:
        resolve_cookie(args)
        return args.func(args)
    except FetchError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return 2
    except KeyboardInterrupt:
        print("\n[ERROR] 用户中断。", file=sys.stderr); return 130

if __name__ == "__main__":
    sys.exit(main())
