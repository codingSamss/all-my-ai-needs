# bird-twitter

## 作用
通过 Bird CLI 只读访问 X/Twitter 内容（推文、搜索、书签、趋势、时间线），并补充 `device_follow` 通知时间线读取脚本。

## 平台支持
- Claude Code（已支持）
- Codex（已支持）

## 工作原理
Skill 调用本地 `bird` 命令并使用浏览器 Cookie 做认证，不提供发帖/评论等写操作。

## 当前可检索范围（只读）
- 单条推文读取：`tweet`、`thread`、`replies`
- 搜索与发现：`search`、`bookmarks`、`trending`、`news`
- 时间线读取：`home`、`home --following`、`device_follow`（通知时间线）
- 用户相关：`user-tweets <username>`、`likes`、`mentions`、`about <username>`
- 关系与列表：`following`、`followers`、`lists`、`list-timeline <list-id-or-url>`

## 明确不支持（当前版本）
- 写操作：发帖、删帖、评论、转推、点赞/取消点赞、关注/取关、私信
- 账号设置变更：通知开关管理、资料修改等
- 非登录态抓取：依赖 Chrome 已登录且可读取 `auth_token`、`ct0` Cookie
- `device_follow` 默认使用内置查询参数；如需与抓包 1:1 对齐，请传入 `--request-url "<完整URL>"`

## 验证命令

```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 bird --cookie-source chrome --timeout 15000 whoami

# device_follow 通知时间线（推荐单次命中命令）
SKILLS_HOME="$HOME/.claude/skills"
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 \
python3 "${SKILLS_HOME}/bird-twitter/scripts/device_follow_timeline.py" \
  --count 3 \
  --plain \
  --cafile "$(python3 -c 'import certifi; print(certifi.where())')"
```

## 使用方式
- 触发词：`read tweet`、`search twitter`、`my bookmarks`、`trending`、`notified timeline`、`device follow`
- 详细命令与触发规则见：`platforms/claude/skills/bird-twitter/SKILL.md`

## 依赖
- Bird CLI（优先仓库内置包 `vendor/bird-macos-universal-v0.8.0.tar.gz`，外部来源可用时可选 `brew install steipete/tap/bird`）
- Chrome 已登录 X/Twitter

## 仓库内置包
- 文件：`vendor/bird-macos-universal-v0.8.0.tar.gz`
- `sha256`：`3d89bb404e8b0ed4ef331f0dc62d873852634ca2a814ae7a4ac7effc114320cf`
- 来源：从本机 Homebrew 缓存提取，用于上游 release 下线后的兜底安装
- 同步策略：该目录为 repo-only 备份资产，AI 同步到 `~/.claude/skills` 时不下发此目录
