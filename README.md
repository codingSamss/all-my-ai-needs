# All My AI Needs（Claude Code + Codex）

这个仓库维护我当前在 Claude Code 与 Codex 上使用的 agent 能力、skills、同步脚本与平台配置。

- Claude 平台真源：`platforms/claude/`
- Codex 平台真源：`platforms/codex/`
- 根脚本入口：`./setup.sh`、`./scripts/sync_to_codex.sh`、`./scripts/bootstrap.sh`
- skill 简介以对应 `SKILL.md` 的 `description` 为准；根 README 负责仓库级总览，平台 README 负责各平台完整清单

## 当前 Skills 总览

以下清单体现当前仓库内 agent 实际拥有的能力。

### 共用 Skills

| Skill | 能力 | 平台 |
| --- | --- | --- |
| `bird-twitter` | 只读访问 X/Twitter 内容 | Claude / Codex |
| `google-workspace` | 只读访问 Gmail、Drive、Docs、Calendar 等 Google Workspace 能力 | Claude / Codex |
| `image-gen` | 图片生成与结构化图表生成 | Claude / Codex |
| `linuxdo` | 只读访问 LINUX DO 论坛 | Claude / Codex |
| `midea-recall-diagnose-playwright` | keyword 检索漏召回排障与请求复现 | Claude / Codex |
| `orbit-os` | OrbitOS Obsidian Vault 共享配置与规范 | Claude / Codex |
| `orbit-session-diary` | 基于本地会话日志生成 Obsidian 日记 | Claude / Codex |
| `peekaboo` | macOS 截图与视觉分析 | Claude / Codex |
| `pinchtab` | PinchTab 优先的浏览器自动化，失败时回退 `playwright-ext` | Claude / Codex |
| `playwright` | MCP-only 真实浏览器自动化 | Claude / Codex |
| `reddit` | 只读访问 Reddit 内容 | Claude / Codex |
| `scrapling` | Scrapling 优先的网页抓取与结构化提取 | Claude / Codex |
| `ui-ux-pro-max` | UI/UX 设计知识检索与落地辅助 | Claude / Codex |
| `video-transcribe` | 视频/音频转录、关键帧分析与总结 | Claude / Codex |
| `xiaohongshu-session-reader` | 小红书 HTTP/API 优先读取，必要时回退 Playwright | Claude / Codex |

### Claude-only

| Skill | 能力 |
| --- | --- |
| `cc-codex-review` | Claude / Codex 协作讨论与 Battle Loop |
| `plugin-manager` | Claude Code 插件管理 |
| `skill-creator` | 创建、优化、评估 skills |

### Codex-only

| Skill | 能力 |
| --- | --- |
| `openai-docs` | OpenAI 官方文档与 API 实现指引 |
| `screenshot` | 系统级截图与区域捕获 |

## 平台能力摘要

### Claude

- `./setup.sh` 将 `platforms/claude` 应用到 `~/.claude`
- 维护 `CLAUDE.md`、`skills/`、`agents/`、`hooks/`、`.mcp.json`、`.claude-plugin/`
- 平台特有能力集中在 `cc-codex-review`、`plugin-manager`、`skill-creator`
- skill 级 `runtime.yaml` 仅同步到对应 skill 目录；平台级 `platforms/claude/runtime.yaml` 仅供仓库内 AI 理解迁移规则

### Codex

- `./scripts/sync_to_codex.sh` 同步 `platforms/codex` 到 `~/.codex`
- 受管 root 仅包含 `AGENTS.md`、`agents/`、`bin/`、`hooks/`、`scripts/`、`rules/`；`config.toml` 默认不覆盖本机
- `~/.codex/skills` 保留 `.system` 与本地未托管内容
- 平台特有能力集中在 `openai-docs`、`screenshot`
- skill 级 `runtime.yaml` 仅同步到对应 skill 目录；平台级 `platforms/codex/runtime.yaml` 仅供仓库内 AI 理解迁移规则

## 快速入口

### Claude

```bash
./setup.sh
./setup.sh list
./setup.sh reddit
```

`./setup.sh` 退出码：

- `0`：全部自动完成
- `2`：存在需手动完成项
- `1`：存在失败项

### Codex

```bash
./scripts/sync_to_codex.sh
./scripts/sync_to_codex.sh --dry-run
./scripts/sync_to_codex.sh --sync-config
```

### 新机一键

```bash
./scripts/bootstrap.sh all
```

## 文档入口

- Claude 平台完整能力与同步说明：`platforms/claude/README.md`
- Codex 平台完整能力与同步说明：`platforms/codex/README.md`
