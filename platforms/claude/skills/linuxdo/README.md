# linuxdo

## 作用
通过 Discourse JSON API + Chrome Cookie 认证只读访问 LINUX DO（linux.do）论坛内容，支持最新帖、热门帖、全文搜索、帖子详情、分类浏览。

## 平台支持
- Claude Code（本实现）
- Codex（独立实现，采用 OAuth + RSS 方案，见 `platforms/codex/skills/linuxdo/`）

## 工作原理
单文件 Python 脚本 `linuxdo.py`，零 pip 依赖（仅标准库 + macOS CommonCrypto ctypes）：
1. 自动从 Chrome 浏览器提取 linux.do 的 Cookie（macOS Keychain + AES-128-CBC 解密）
2. 通过 Discourse JSON API 获取论坛数据
3. urllib 请求 + curl 自动回退，支持代理配置

## 与 Codex 版本的差异

| 方面 | Codex | Claude (本方案) |
|------|-------|----------------|
| 认证 | OAuth PKCE (connect.linux.do) | Chrome Cookie 自动提取 |
| API | RSS/HTML 解析 | Discourse JSON API |
| 脚本数 | 2 个 (oauth + feed) | 1 个 (统一) |
| 外部依赖 | OAuth client_id/secret | 无 (Chrome 已登录即可) |
| 搜索 | RSS 关键词匹配 | search.json 全文搜索 |
| 受限内容 | 无法访问 | Chrome Cookie 可访问 |

## 配置命令

```bash
./setup.sh linuxdo
# 或直接执行
platforms/claude/skills/linuxdo/setup.sh
```

## 配置脚本行为

- 退出码：`0` 自动完成，`2` 需手动补齐，`1` 执行失败
- 自动检查项：
  - Python3 是否可用（缺失时尝试 `brew install python3`）
  - scripts/ 同步到 `~/.claude/skills/linuxdo/scripts/`
  - Chrome Cookies 数据库是否存在
  - linux.do API 可达性（含代理回退）
  - Chrome Cookie 认证测试（非阻塞，失败仍允许访问公开内容）

## 验证命令

```bash
# 查看登录身份
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py whoami

# 查看最新帖子
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py latest --limit 3

# 搜索
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py search "Claude" --limit 5

# 帖子详情
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py topic 1611298 --posts 3

# 分类列表
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py category

# 分类帖子
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py category develop --limit 5

# 热门帖子
python3 ~/.claude/skills/linuxdo/scripts/linuxdo.py top --period weekly
```

## 使用方式
- 触发词：`linuxdo 最新帖子`、`搜索 linuxdo`、`查看帖子`、`l站热门`、`linuxdo 分类`
- 详细命令与触发规则见：`platforms/claude/skills/linuxdo/SKILL.md`

## 依赖
- Python3（标准库即可，零 pip 依赖）
- macOS（Chrome Cookie 提取依赖 Keychain + CommonCrypto）
- Chrome 浏览器已登录 linux.do（可选，不登录仍可访问公开内容）
