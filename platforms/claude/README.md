# Claude 平台目录（claude）

`platforms/claude` 是 Claude 平台专属真源。这个 README 负责展示当前 Claude agent 的完整能力与同步方式。仓库按 `platform-first` 维护：Claude 只关心 `platforms/claude` 下的内容，不再依赖 `shared/skills/`。

## 同步入口

```bash
./scripts/syncctl.sh check --direction repo-to-local --platform claude --scope all
./scripts/syncctl.sh apply --plan-id <plan_id> --approve-token <token>
./setup.sh
./setup.sh list
./setup.sh <skill-name>
```

退出码：

- `0`：自动完成
- `2`：需手动补齐
- `1`：失败

说明：

- `syncctl` 是日常一致性检查与执行入口（最小同步口径 + 两阶段审批）
- 处理同步/提交/推送请求时，若用户只说“看下本地跟仓库有什么内容需要同步的”等未授权写入请求，默认先执行 `check` 并汇总，再等待用户审批后执行 `apply` / `commit` / `push`
- `setup.sh` 主要用于 bootstrap / 灾备 fallback

## 当前 Skills

| Skill | 能力 | 运行说明 |
| --- | --- | --- |
| `bird-twitter` | 只读访问 X/Twitter 内容 | 依赖 Bird CLI（仓库内置包优先） |
| `cc-codex-review` | Claude / Codex 协作讨论与 Battle Loop | 依赖 CodexMCP 与 topic-manager |
| `context-hub` | 通过 chub 检索版本化 API/SDK 文档与技能内容 | 依赖 Node.js/npm 与 chub CLI |
| `google-workspace` | 只读访问 Google Workspace 内容 | 依赖 gogcli 与 OAuth 登录态 |
| `image-gen` | 图片生成与结构化图表生成 | 依赖图片 provider 配置 |
| `fireworks-tech-graph` | 结构化技术图生成（架构图/流程图/时序图/泳道图，SVG+PNG） | 依赖 `python3` 与 `rsvg-convert` |
| `linuxdo` | 只读访问 LINUX DO 论坛 | 依赖 Chrome Cookie |
| `llm-wiki` | 用 analysis -> generation 维护 Karpathy 风格 markdown wiki | 平台本地真源：`platforms/claude/skills/llm-wiki` |
| `midea-recall-diagnose-playwright` | keyword 漏召回排查、回放与 trace/ELK/ES 取证 | 依赖 Playwright 会话与本地脚本 |
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
- `./setup.sh` 负责在 bootstrap / 灾备场景下把 `platforms/claude` 应用到 `~/.claude`
- `platforms/claude/.mcp.json` 已内置 MCP：`playwright-ext`、`chrome-devtools`、`playwright`、`context7`、`tavily`
- skill 若需要依赖、手动步骤、验证命令，统一写入 repo 中对应 skill 目录下的 `runtime.yaml`
- 平台级 `platforms/claude/runtime.yaml` 仅用于仓库内 AI 理解迁移规则，不会同步到 `~/.claude` 根目录
- skill 级 `runtime.yaml` 仅保留在 repo，不同步到 `~/.claude/skills/<skill>/`
