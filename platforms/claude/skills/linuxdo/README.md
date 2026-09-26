# linuxdo

## 作用
通过 Discourse JSON API + Chrome Cookie 认证只读访问 LINUX DO（linux.do）论坛内容，支持最新帖、热门帖、全文搜索、帖子详情、分类浏览。

## 平台支持
- Claude Code（本实现）
- Codex（同样采用 Chrome Cookie + Discourse JSON API，见 `platforms/codex/skills/linuxdo/`）

## 工作原理
单文件 Python 脚本 `linuxdo.py`，零 pip 依赖（仅标准库 + macOS CommonCrypto ctypes）：
1. 自动从 Chrome 浏览器提取 linux.do 的 Cookie（macOS Keychain + AES-128-CBC 解密）
2. 通过 Discourse JSON API 获取论坛数据
3. urllib 请求 + curl 自动回退，支持代理配置

## 平台实现

Claude Code 与 Codex 均使用单文件 `linuxdo.py`、Chrome Cookie 认证和 Discourse JSON API，支持 `search.json` 全文搜索；可访问内容受当前登录账号权限限制。无认证时仅可访问公开内容。

两平台按各自目录维护与安装：Claude Code 使用 `~/.claude/skills/linuxdo/`，Codex 使用 `${CODEX_HOME:-$HOME/.codex}/skills/linuxdo/`；具体入口以对应平台的 `SKILL.md` 为准。

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
