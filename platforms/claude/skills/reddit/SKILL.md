---
name: reddit
description: "Read Reddit content through OpenCLI using the user's Chrome logged-in session. Actions: search posts, read posts and comments, browse subreddit/hot/popular feeds. Keywords: reddit, subreddit, post, comment, search reddit, hot posts, popular posts."
---

# Reddit Skill (Read-Only)

Use OpenCLI for Reddit read-only tasks. This replaces the previous Composio MCP route because the local Chrome session path is more direct and avoids a remote MCP/OAuth dependency.

## When To Use

Triggered by:
- "search reddit [query]", "find on reddit [query]"
- "read reddit post [url/id]", "show reddit post"
- "reddit comments [url/id]", "show comments on reddit"
- "reddit hot", "reddit popular", "hot posts on r/[subreddit]"
- "browse r/[subreddit]", "latest on r/[subreddit]"

## Prerequisites

1. Node.js and npm are installed.
2. OpenCLI is installed: `npm install -g @jackwener/opencli`
3. The OpenCLI Chrome extension is installed manually from the Chrome Web Store.
4. Chrome is open and logged into `reddit.com`.
5. If Reddit is blocked by the current network, use the local proxy configured for this machine.

Check status without starting or changing the daemon:

```bash
opencli daemon status
```

Do not run `opencli doctor` for routine checks; it can start the daemon.

## Commands

Search posts:

```bash
opencli reddit search "<query>" -f yaml
```

Read a post and comments:

```bash
opencli reddit read "<post_id_or_url>" -f yaml
```

Browse a subreddit:

```bash
opencli reddit subreddit "<subreddit>" -f yaml
```

Hot and popular feeds:

```bash
opencli reddit hot -f yaml
opencli reddit popular -f yaml
```

Subreddit metadata:

```bash
opencli reddit subreddit-info "<subreddit>" -f yaml
```

## Fallback

Use `rdt-cli` only when OpenCLI is not viable, such as a server or existing non-desktop setup:

```bash
rdt search "<query>" --limit 10
rdt read "<post_id_or_url>"
rdt sub "<subreddit>" --limit 20
rdt popular --limit 10
```

`rdt-cli` also requires logged-in Reddit cookies. Anonymous Reddit access is not treated as a supported path.

## Safety

- Read-only only: search, browse, read posts and comments.
- Do not post, comment, vote, subscribe, or message users.
- Do not bypass captcha or automated risk controls.
- If OpenCLI returns `AUTH_REQUIRED`, ask the user to refresh Reddit login in Chrome.
