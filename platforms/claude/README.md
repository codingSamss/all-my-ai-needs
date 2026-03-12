# Claude 平台目录（claude）

`platforms/claude` 是 Claude 平台唯一真源。这个 README 负责展示当前 Claude agent 的完整能力与同步方式。

## 同步入口

```bash
./setup.sh
./setup.sh list
./setup.sh <skill-name>
```

退出码：

- `0`：自动完成
- `2`：需手动补齐
- `1`：失败

## 当前 Skills

以下技能简介以各自 `SKILL.md` 的 `description` 为准，并压缩为便于浏览的摘要。

| Skill | 能力 | 运行说明 |
| --- | --- | --- |
| `bird-twitter` | 只读访问 X/Twitter 内容 | 依赖 Bird CLI |
| `cc-codex-review` | Claude / Codex 协作讨论与 Battle Loop | 依赖 CodexMCP 与 topic-manager |
| `google-workspace` | 只读访问 Google Workspace 内容 | 依赖 gogcli 与 OAuth 登录态 |
| `image-gen` | 图片生成与结构化图表生成 | 依赖图片 provider 配置 |
| `linuxdo` | 只读访问 LINUX DO 论坛 | 依赖 Chrome Cookie |
| `midea-recall-diagnose-playwright` | keyword 检索漏召回排障与请求复现 | 依赖 Playwright 会话与本地脚本 |
| `orbit-os` | OrbitOS Obsidian Vault 共享配置与规范 | 供 orbit-* 系列 skill 引用 |
| `orbit-session-diary` | 基于本地会话日志生成 Obsidian 日记 | 依赖本地 jsonl 与目标 Vault |
| `peekaboo` | macOS 截图与视觉分析 | 依赖 Peekaboo |
| `pinchtab` | PinchTab 优先的浏览器自动化 | PinchTab + `playwright-ext` fallback |
| `playwright` | MCP-only 真实浏览器自动化 | 依赖 `playwright-ext` 浏览器扩展会话 |
| `plugin-manager` | Claude Code 插件管理 | 面向 `.claude-plugin` 体系 |
| `reddit` | 只读访问 Reddit 内容 | 依赖 Composio MCP |
| `scrapling` | Scrapling 优先的网页抓取与结构化提取 | `scrapling[fetchers]` + `playwright-ext` |
| `skill-creator` | 创建、优化、评估 skills | 用于 skill 设计与迭代 |
| `ui-ux-pro-max` | UI/UX 设计知识检索与落地辅助 | 依赖本地 scripts/知识库 |
| `video-transcribe` | 视频/音频转录、关键帧分析与总结 | 依赖 yt-dlp / ffmpeg / Groq |
| `xiaohongshu-session-reader` | 小红书 HTTP/API 优先读取 | Chrome Cookie + Playwright fallback |

## 平台能力资产

- 受管内容：`CLAUDE.md`、`skills/`、`agents/`、`hooks/`、`.mcp.json`、`.claude-plugin/`
- `./setup.sh` 负责把 `platforms/claude` 应用到 `~/.claude`
- skill 若需要依赖、手动步骤、验证命令，统一写入 skill 目录下的 `runtime.yaml`
- 平台级 `platforms/claude/runtime.yaml` 仅用于仓库内 AI 理解迁移规则，不会同步到 `~/.claude` 根目录
- skill 级 `runtime.yaml` 仅会同步到 `~/.claude/skills/<skill>/runtime.yaml`
