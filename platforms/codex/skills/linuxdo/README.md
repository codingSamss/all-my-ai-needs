# linuxdo

## 作用
通过 Discourse JSON API + Chrome Cookie 认证只读访问 LINUX DO（linux.do）论坛内容，支持最新帖、热门帖、全文搜索、帖子详情、分类浏览。

## 平台支持
- Codex（已支持）

## 工作原理
单文件 Python 脚本 `linuxdo.py`，零 pip 依赖（仅标准库 + macOS CommonCrypto ctypes）：
1. 自动从 Chrome 提取 linux.do Cookie（macOS Keychain + AES-128-CBC 解密）
2. 走 Discourse JSON API（`latest.json` / `top.json` / `search.json` / `t/{id}.json` / `categories.json`）
3. 自动降级 `urllib + curl` 双通道请求并处理 Cloudflare challenge

## 验证命令

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SCRIPT="$CODEX_HOME/skills/linuxdo/scripts/linuxdo.py"

# 身份验证
python3 "$SCRIPT" whoami

# 最新帖子
python3 "$SCRIPT" latest --limit 3

# 搜索
python3 "$SCRIPT" search "Claude" --limit 5

# 目标帖子
python3 "$SCRIPT" topic 1611298 --posts 3
```

## 使用方式
- 触发词：`linuxdo 最新帖子`、`搜索 linuxdo`、`查看帖子`、`l站热门`、`linuxdo 分类`
- 详细命令与触发规则见：`platforms/codex/skills/linuxdo/SKILL.md`

## 依赖
- Python3
- macOS Keychain（用于自动解密 Chrome Cookie）
- Chrome 已登录 linux.do（可选，不登录仍可访问公开内容）
