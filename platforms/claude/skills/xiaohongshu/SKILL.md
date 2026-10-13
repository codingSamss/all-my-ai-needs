---
name: xiaohongshu
description: "Read Xiaohongshu (小红书) through OpenCLI using the user's Chrome logged-in session. Search notes, read note details and comments, browse feed and user notes, or download note media. Keywords: xiaohongshu, xhs, 小红书, 红书, 笔记, 评论, feed."
---

# Xiaohongshu Skill (Read-Only)

Use OpenCLI as the single supported Xiaohongshu implementation. The previous HTTP/API and Chrome Cookie DB extraction path was removed because Xiaohongshu frequently requires browser-side login verification and risk-control handling.

## When To Use

Triggered by:
- "小红书搜 [query]", "search xiaohongshu [query]"
- "读小红书笔记", "read xhs note [url]"
- "小红书评论", "xhs comments"
- "小红书 feed", "小红书首页"
- "小红书用户主页", "xhs user"

## Prerequisites

1. Node.js and npm are installed. OpenCLI 1.8.8 requires Node.js >=20.18.1.
2. OpenCLI is installed. Before installing or upgrading, read [the upgrade review](references/opencli-upgrade.md). The reviewed combination is OpenCLI 1.8.8 with actual runtime dependencies `undici 7.29.1` and `js-yaml 4.3.2`; an ordinary 1.8.8 installation does not include this dependency correction. Reinstalling or updating can overwrite the local correction, so recheck the actual dependencies and current advisories.
3. The OpenCLI Chrome extension is installed manually from the Chrome Web Store.
4. Chrome is open and logged into Xiaohongshu.

Check status without starting or changing the daemon:

```bash
node --version
opencli --version
opencli daemon status
```

Do not run `opencli doctor` for routine checks; it can start the daemon.

## Commands

Search notes:

```bash
opencli xiaohongshu search "<query>" -f yaml
```

On a separately reviewed installation that supports the OpenCLI 1.8.8 search options, filter recent image notes:

```bash
opencli xiaohongshu search "<query>" --sort latest --note-type image --publish-time week --limit 5 -f yaml
```

Check `opencli xiaohongshu search --help` before using these options. Older versions may not support them. Location filters can require browser geolocation permission; do not grant that permission just to make a search succeed.

Read a note:

```bash
opencli xiaohongshu note "<full_note_url_with_xsec_token>" -f yaml
```

Read comments:

```bash
opencli xiaohongshu comments "<full_note_url_with_xsec_token>" --limit 5 -f yaml
```

Browse feed:

```bash
opencli xiaohongshu feed -f yaml
```

Read a user's public notes:

```bash
opencli xiaohongshu user "<user_id>" -f yaml
```

Download media from a note:

```bash
opencli xiaohongshu download "<full_note_url_with_xsec_token>" --output "./xiaohongshu-downloads" -f yaml
```

`note` and `comments` require a full signed note URL from search, feed, or profile results; a bare note ID is insufficient. `download` also accepts note share links, but a profile share link is not a note.

## Recommended Workflows

### Preflight

1. Check that the daemon and Chrome extension are available:

```bash
opencli daemon status
```

2. Check Xiaohongshu login state before reading search results, profiles, or notes:

```bash
opencli xiaohongshu whoami -f yaml --window background --site-session persistent --trace off
```

`whoami` checks the creator-side session; success does not prove every content page is accessible. If a target page returns `AUTH_REQUIRED`, stop the batch and ask the user to refresh login in Chrome. Preserve network/service errors as such; do not interpret every `whoami` failure as expired login. Do not switch to cookie extraction or unofficial APIs.

If OpenCLI returns `BROWSER_CONNECT` or cannot bind `127.0.0.1:19825`, the daemon may be blocked by the current sandbox. Start or check the daemon from an unrestricted host shell when available, then rerun the same OpenCLI command. Do not use `opencli doctor` for routine checks.

### Risk Controls and Local Evidence

- OpenCLI 1.8.8 internally retries `note`, `comments`, and `download` at most once after an 8-18 second cooldown on a detected soft block. Older versions may fail immediately. This is not a cross-command rate limiter or a guarantee against account restrictions.
- If a command returns `SECURITY_BLOCK`, or a captcha/account warning appears, stop the whole batch. Do not wrap it in an outer retry loop or switch accounts, sessions, IPs, or tools to continue through the restriction. Leave verification to the user.
- Run batch commands serially with a deliberate pause between notes. Start with a small probe and expand only to the requested scope; no particular delay guarantees safety.
- Keep trace capture off by default. Enable `--trace retain-on-failure` only for a bounded diagnostic run. Signed URLs, manifests, traces, screenshots, and account data stay local; redact tokens and identity details from shared reports and never commit them.

### Profile Share Links

Do not pass a profile `xhslink.com/m/...` URL directly to `opencli xiaohongshu user` and assume the short-link tail is the user id. In practice, OpenCLI may incorrectly navigate to:

```text
https://www.xiaohongshu.com/user/profile/<short-link-tail>
```

If the trace shows a `404` for that URL, the `EMPTY_RESULT` error is probably a bad profile id, not proof that the user has no public notes.

For profile share links, first resolve the canonical profile URL:

- Prefer a real URL like `https://www.xiaohongshu.com/user/profile/<user_id>?xsec_token=...`.
- If only a short link is available, ask the user to open it while logged in, then read the final URL from the current Chrome tab or recent Chrome history.
- Use Chrome only for URL resolution or visible-page confirmation. Keep Xiaohongshu data extraction in OpenCLI.

After resolving the canonical profile URL, probe the profile:

```bash
opencli xiaohongshu user "<canonical_profile_url>" --limit 5 -f yaml --window background --site-session persistent --trace off
```

If `search "<creator_name>"` returns `[]`, do not conclude the creator is missing. Try the canonical profile URL or the user's browser history/open tab instead.

### Batch Profile Media Download

For bulk image download from a profile, use a staged flow:

1. Probe the profile with `--limit 5`.
2. Download 1-3 notes first to verify media extraction and local file layout.
3. Save a local manifest before full download, using the user-requested count rather than an automatic large batch:

```bash
opencli xiaohongshu user "<canonical_profile_url>" --limit "<requested_limit>" -f json --window background --site-session persistent --trace off > notes-manifest.json
```

4. Download from manifest URLs, not note ids alone. The manifest URLs usually include the required `xsec_token`.
5. Write a token-redacted status log per note. A confirmed deleted note or missing media may be skipped; `SECURITY_BLOCK`, login loss, captcha, or account warnings stop the entire batch. Do not continue past these as ordinary per-note failures.
6. Preserve the raw download directory. If the user wants clean names, copy into a separate `named/` directory instead of destructively renaming raw files.

Suggested clean naming:

```text
named/
  001_<article-title>/
    <article-title>_1.jpg
    <article-title>_2.jpg
```

When generating filenames, sanitize filesystem-illegal characters such as `/`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, and control characters. Keep a rename manifest that maps source files to named files.

### Interpreting Download Results

- `No media found` on a profile share link usually means the input is a profile, not a note. Resolve the profile, list note URLs, then download each note URL.
- `EMPTY_RESULT` from `user` with a profile short link usually means the short-link tail was treated as a bad user id. Inspect the trace before reporting "no public notes".
- A successful `download` command writes files locally and is still read-only with respect to Xiaohongshu. It must not post, like, follow, comment, delete, or publish anything.

## Notes

- Preserve the complete signed note URL, including `xsec_token` and any `xsec_source`, when passing results between commands.
- If OpenCLI returns `AUTH_REQUIRED`, ask the user to refresh Xiaohongshu login in Chrome.
- Do not use HTTP/API scraping, Chrome Cookie DB extraction, `xiaohongshu-mcp`, or `xhs-cli` as hidden fallbacks.
- Do not post, comment, like, favorite, follow, or bypass captcha/risk controls.
- Never run write commands such as `publish`, `delete-note`, `follow`, or `unfollow` unless the user explicitly asks for that exact action and the normal browser safety confirmation rules are satisfied.
- For batch tasks, report the canonical profile URL or user id used, manifest count, success/failure count, output directories, and whether any temporary daemon/browser session was left running.
