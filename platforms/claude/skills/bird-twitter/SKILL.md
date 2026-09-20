---
name: bird-twitter
description: "Read X/Twitter content via Bird CLI. Actions: read tweets, search, view all bookmarks or bookmark folders, trending, news, timeline, mentions, lists. Keywords: twitter, x, tweet, trending, bookmarks, bookmark folder, 收藏夹, timeline."
---

# Bird Twitter Skill (Read-Only)

Read X/Twitter content using the Bird CLI tool. This skill only exposes read-only operations to avoid account suspension risks.

## When to Use This Skill

Triggered by:
- "read tweet [id/url]", "show tweet [id/url]"
- "search twitter [query]", "search x [query]"
- "my bookmarks", "twitter bookmarks"
- "bookmark folder", "收藏夹文件夹", "待办收藏夹", "推特收藏夹中的[folder name]"
- "trending", "twitter trends", "what's trending"
- "twitter news", "x news"
- "timeline", "i/timeline", "通知时间线", "device follow"
- "for you", "home", "home timeline", "首页推荐"
- "following", "following timeline", "首页关注流"
- "user timeline [username]", "timeline [username]", "user tweets [username]"
- "my mentions", "twitter mentions"
- "twitter lists", "my lists"
- "my feed"

## Terminology Mapping (Unified)

- `timeline` -> `x.com/i/timeline` (`device_follow` endpoint)
- `for you` / `首页推荐` / `home` -> `bird home -n 20`
- `following` / `首页关注流` -> `bird home --following -n 100`
- `timeline [username]` -> `bird user-tweets <username> -n 20`

Default rule: if user says only `timeline` with no qualifier, treat it as `i/timeline`.

## Prerequisites

1. Bird CLI 安装：**新机器上运行一次 `scripts/install_local.zsh` 即可**——解包仓库内置包 `vendor/bird-macos-universal-v0.8.0.tar.gz`、重签、把 wrapper 与凭据工具链接进 `~/.local/bin`，幂等可重复运行。外部来源可用时也可选 `brew install steipete/tap/bird`。
   - 运行件布局：`~/.local/bin/bird` 与 `~/.local/bin/bird-x-cookies-to-keychain` 都是指向本 skill `scripts/` 下源文件的软链，真二进制是 `~/.local/bin/bird-bin`。源文件随 skill 入仓、软链由安装脚本重建，所以换机器只需「同步仓库 + 跑一次脚本 + 存一次凭据」
   - **macOS 26+ 解包后必须重签一次**（安装脚本已含此步）：包内二进制是 linker-signed adhoc 签名，新系统判定其无效并直接 SIGKILL，表现为任何子命令都零输出、退出码 137。执行 `codesign -f -s - <bird 路径>` 即可，二进制内容不变。包内那份签名本身就是坏的，重新解包不解决问题。
2. 认证凭据按 环境变量 -> 钥匙串 -> 浏览器 cookie 库 的顺序解析：
   - 主路径是钥匙串，Claude Code 一侧不需要任何系统授权。填充方式二选一：
     - 自动（推荐）：在一个持有完全磁盘访问权限的终端里运行 `bird-x-cookies-to-keychain`。凭据写入本地登录钥匙串（`login.keychain-db`），**不随 iCloud 同步**，每台机器各存一次，它从 Chrome 提取后直接写入钥匙串，凭据过期时重跑同一条即可刷新。授权对象选终端而非 Claude Code——终端路径固定，一次永久有效
     - 手动：值取自 Chrome DevTools（F12 -> Application -> Cookies -> `https://x.com`）
       ```
       security add-generic-password -U -a "$USER" -s bird-x-auth-token -w
       security add-generic-password -U -a "$USER" -s bird-x-ct0 -w
       ```
   - `~/.local/bin/bird` 是一层 wrapper，取出凭据后经 `AUTH_TOKEN` / `CT0` 环境变量交给真二进制 `bird-bin`。用环境变量而非命令行参数有两个原因：凭据不进 argv（`ps` 默认输出看不到，但 `ps eww` 仍能读到进程环境——暴露面只是小一档，不是消失）；不受全局开关与子命令先后顺序的影响（`bird --timeout 20000 whoami` 这类写法会让基于位置的注入失效）。`bird-bookmark-folders` skill 共用同一对钥匙串条目
   - **凭据失效（401 / `Could not authenticate you`）时的自动恢复**：在 Claude 桌面 app 的终端面板里运行 `bird-x-cookies-to-keychain`（`mcp__terminal__run_in_terminal`），无需用户介入。该面板的 shell 挂在桌面 app 本体（`com.anthropic.claudefordesktop`）名下并继承其完全磁盘访问权限；Bash 工具继承的则是 `com.anthropic.claude-code` helper 的身份，没有该权限——这是两条路唯一的差别，也是刷新必须走终端面板的原因
   - 回退路径是让 bird 自己读浏览器 cookie 库，这需要给当前 Claude Code bundle 完全磁盘访问权限。该授权绑定调用方路径与签名，而 Claude Code 每次升级都换目录，因此会反复失效——不要依赖它
3. In this environment, network access to X should go through local proxy:
   - `HTTP_PROXY=http://127.0.0.1:7897`
   - `HTTPS_PROXY=http://127.0.0.1:7897`
4. Run `HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 whoami` to verify authentication；输出首行 `📍 env AUTH_TOKEN` 表示走的是钥匙串凭据，`📍 chrome` 表示回退到了 cookie 库
5. If Python requests fail with SSL certificate verification behind proxy, ensure `certifi` is available (`python3 -c "import certifi; print(certifi.where())"`); when needed, pass the CA bundle explicitly via `--cafile`.

## Global Options

All commands should use:
- proxy env (`HTTP_PROXY` / `HTTPS_PROXY`)
- `--cookie-source chrome` to only use Chrome cookies (skip Safari/Firefox)。**凭据走钥匙串时该选项无实际作用**：wrapper 已把 `AUTH_TOKEN`/`CT0` 注入环境，bird 优先用环境变量，不会去读任何浏览器 cookie 库
- `--timeout 15000` to avoid hanging requests

Recommended command prefix:
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 <command>
```

For `device_follow_timeline.py`:
- In this proxy environment, prefer a single-shot command with explicit `--cafile`; do not first try a bare command and then retry.
- Script now auto-detects `certifi` CA bundle and logs `SSL trust source`.
- You can explicitly force trust source with `--cafile <path>` / `--capath <dir>`; environment variables `SSL_CERT_FILE` / `SSL_CERT_DIR` are still supported.
- Emergency fallback only: set `BIRD_INSECURE_SSL=1` to retry once without SSL verification.

Example:
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 home -n 20
```

## Commands

### 1. Check Auth Status
**Triggers:** "twitter auth", "bird whoami", "check twitter login"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 whoami
```

### 2. Read Tweet
**Triggers:** "read tweet [id]", "show tweet [url]", "get tweet"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 read <tweet-id-or-url>
```
Options: `--plain` for stable output without emoji/color
Notes:
- `--plain` 仅用于临时阅读/命令行快速查看，不得用于“收录/归档/完整保存”任务。
- 归档任务必须使用 `--json-full`，并从 `article.article_results.result.content_state`（正文结构）+ `media_entities`（图片资源）恢复图文顺序。

### 2b. Archive Tweet/Article (Text + Media)
**Use when:** 用户要求“收录/归档/完整保存/原文保留（含图）”
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 read --json-full <tweet-id-or-url>
```
Requirements:
- 保留原文结构（标题、列表、引用、代码块）
- 图片按原文顺序本地化并在文内原位引用
- 必做三数一致校验：预期图片数 = 下载成功数 = 文内引用数
- 结构重建必须以 `content_state.blocks` 为唯一顺序源，禁止用 `--plain` 文本推断结构
- `atomic` 块类型必须从 `entityMap.value.type` 判定（`MEDIA` / `MARKDOWN` / `DIVIDER`），禁止猜测
- `MEDIA` 必须通过 `mediaItems[].mediaId -> media_entities[].media_info.original_img_url` 映射原图
- 下载前先清理目标目录中“同编号不同扩展名”的旧文件，避免 `img-N.jpg/png` 并存
- 收尾必须做块级一致性校验：`MEDIA=标准图片引用数`、`MARKDOWN=代码块数`、`DIVIDER=分隔线数`
- 若存在人工补充图，必须显式标注“补充内容，非 X 原文正文”
- 最后执行一次未引用资产扫描，删除 `assets/hitw93-*/` 下未被任何 `.md` 引用的冗余文件

### 3. Read Thread
**Triggers:** "read thread [id]", "show thread [url]"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 thread <tweet-id-or-url>
```

### 4. Read Replies
**Triggers:** "show replies to [id]", "tweet replies"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 replies <tweet-id-or-url>
```
Notes:
- `replies` does not support `-n` / `--count` in current Bird CLI versions.
- Use `--max-pages <number>` or `--all` to control pagination when needed.

### 5. Search
**Triggers:** "search twitter [query]", "search x [query]", "find tweets about"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 search "<query>" -n 10
```

### 6. View Bookmarks
**Triggers:** "my bookmarks", "twitter bookmarks", "saved tweets"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 bookmarks -n 20
```
Notes:
- `bookmarks` without `--folder-id` reads **All Bookmarks**, not a user-created bookmark folder.
- If the user names a folder such as `待办`, do not summarize All Bookmarks as a substitute. Resolve the folder id first, then read that folder.

### 6b. View Bookmark Folder
**Triggers:** "bookmark folder [name/id]", "收藏夹文件夹", "待办收藏夹", "推特收藏夹中的代办/待办"

If the folder URL or numeric id is known:
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 bookmarks --folder-id <folder-id-or-url> -n 20
```

For a complete folder read:
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 bookmarks --folder-id <folder-id-or-url> --all --max-pages 5 --json
```

Folder-id workflow:
1. Prefer a visible folder URL such as `https://x.com/i/bookmarks/<id>`; `bird` accepts either the numeric id or the full URL.
2. If only the folder name is known, try `opencli twitter bookmark-folders` to list folder ids. This command is read-only, but it may fail with HTTP 404 when X rotates the GraphQL operation.
3. If `opencli twitter bookmark-folders` fails, do not fall back to All Bookmarks. The reliable way to list folder ids is the `bird-bookmark-folders` skill (`python3 scripts/bookmark_folders.py list`), which calls `BookmarkFoldersSlice` directly. Failing that, get candidate ids from an already-open Chrome/X URL or browser history, then validate with `bird ... bookmarks --folder-id <id> -n 3 --plain`.
4. Match the candidate folder by comparing the first returned tweets with the user's screenshot or named folder context before producing a summary.
5. After `--all --max-pages N --json`, inspect `nextCursor`; if it is non-empty and the user asked for exhaustive results, increase `--max-pages`.

### 7. View Trending/News
**Triggers:** "trending", "twitter trends", "what's trending", "twitter news", "x news"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 news
```

### 8. View Home Timeline
**Triggers:** "home", "home timeline", "my feed", "for you", "首页推荐"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 home -n 20
```

### 8b. View Following Timeline
**Triggers:** "following", "following timeline", "首页关注流", "关注时间线"

Following 时间线按时间排序，是日常信息获取的主要入口。默认拉 100 条以覆盖近一天的内容，避免遗漏。
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 home --following -n 100
```

### 8c. View i/timeline (Device Follow)
**Triggers:** "timeline", "i/timeline", "notified timeline", "device follow", "通知时间线"

`x.com/i/timeline` 与 `home --following` 不是同一数据源。该命令直接请求 `device_follow` REST endpoint，默认读取 20 条。
```bash
SKILLS_HOME="$HOME/.claude/skills"
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 \
python3 "${SKILLS_HOME}/bird-twitter/scripts/device_follow_timeline.py" \
  --count 20 \
  --cafile "$(python3 -c 'import certifi; print(certifi.where())')"
```

如需严格对齐抓包参数，传入完整请求 URL：
```bash
SKILLS_HOME="$HOME/.claude/skills"
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 \
python3 "${SKILLS_HOME}/bird-twitter/scripts/device_follow_timeline.py" \
  --count 20 \
  --request-url "$BIRD_DEVICE_FOLLOW_URL"
```

### 9. View User Tweets
**Triggers:** "tweets from [username]", "timeline [username]", "[username]'s tweets"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 user-tweets <username> -n 20
```

### 10. View Likes
**Triggers:** "my likes", "liked tweets"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 likes -n 20
```

### 11. View Mentions
**Triggers:** "my mentions", "twitter mentions", "who mentioned me"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 mentions -n 20
```

### 12. View Lists
**Triggers:** "my lists", "twitter lists"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 lists
```

### 13. View List Timeline
**Triggers:** "list timeline [id]", "tweets from list"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 list-timeline <list-id-or-url> -n 20
```

### 14. View Following
**Triggers:** "who do I follow", "my following"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 following -n 50
```

### 15. View Followers
**Triggers:** "my followers", "who follows me"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 followers -n 50
```

### 16. User Info
**Triggers:** "about [username]", "user info [username]"
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 about <username>
```

## Output Options (Command-Specific)

Global output flag:
- `--plain` - Stable output without emoji or color (good for parsing)
- `--plain` 不可作为归档源（会丢失图文结构/媒体信息）

Count flags (supported by many but not all commands):
- `-n <number>` or `--count <number>` - Limit number of results
- Commonly supported: `home`, `search`, `bookmarks`, `likes`, `mentions`, `user-tweets`, `list-timeline`, `following`, `followers`, `lists`, `news`

Pagination-only commands:
- `replies` / `thread` use `--max-pages <number>` or `--all` instead of `-n` / `--count`

When in doubt, check command-specific help first:
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --timeout 15000 <command> --help
```

## Important Notes

- This skill is READ-ONLY to avoid account suspension
- Uses unofficial X GraphQL API - may break without notice
- Requires browser login to X for cookie authentication
- If authentication fails, log into X in your browser and try again
- 若要自己发 GraphQL 请求，bearer token 一律引用 `device_follow_timeline.DEFAULT_BEARER_TOKEN`，不要手抄：它在 `device_follow_timeline.py:29-31` 是跨两行的字符串拼接，`grep` 单行只会拿到前半截，用半截 token 会稳定返回 `401 code 32 Could not authenticate you`
- 收藏夹的**写操作**（新建收藏夹、把书签在收藏夹间移动）见 `bird-bookmark-folders` skill；本 skill 只做读取

## Excluded Commands (High Risk)

The following commands are intentionally NOT exposed due to account suspension risk:
- `bird tweet` - Post new tweets
- `bird reply` - Reply to tweets
- `bird follow` / `bird unfollow` - Follow/unfollow users
- `bird unbookmark` - Remove bookmarks
