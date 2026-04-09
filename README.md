# All My AI Needs（Claude Code + Codex + Hermes）

这个仓库维护我当前在 Claude Code、Codex 与 Hermes 上使用的 agent 能力、skills、同步脚本与平台配置。其中 Hermes 当前以“文档基线”方式纳入仓库：记录本机目录、迁移步骤与差异基线，但不提供自动同步脚本。除平台专属 skill 外，仓库也允许少量经批准的共享 skill 真源（当前仅 `llm-wiki`）。

- 共享 skill 真源：`shared/skills/`（当前仅 `llm-wiki`）
- Claude 平台真源：`platforms/claude/`
- Codex 平台真源：`platforms/codex/`
- Hermes 文档基线：`platforms/hermes/`（记录当前本机使用态与迁移说明）
- 根脚本入口：`./setup.sh`、`./scripts/sync_to_codex.sh`、`./scripts/bootstrap.sh`
- skill 简介以对应 `SKILL.md` 的 `description` 为准；根 README 负责仓库级总览，平台 README 负责各平台完整清单

默认同步策略：
- 日常共享 skill 同步优先由 AI 手工 diff 后做最小落盘，不直接跑脚本做镜像。
- `runtime.yaml` 只保留在 repo，不下发到 `~/.claude`、`~/.codex`、`~/.hermes`。
- `./setup.sh`、`./scripts/sync_to_codex.sh`、`./scripts/bootstrap.sh` 仅作为新机初始化、灾备恢复、整个平台重建的 fallback。

## 当前 Skills 总览

以下清单体现当前仓库内 agent 实际拥有的能力。

### 共用 Skills

| Skill | 能力 | 平台 |
| --- | --- | --- |
| `bird-twitter` | 只读访问 X/Twitter 内容 | Claude / Codex |
| `bird-twitter-bookmarks` | 使用 Field Theory CLI 同步/检索/分类 X 收藏夹本地数据，并支持 unknown 条目 L2 细分标签与复核队列 | Claude / Codex |
| `context-hub` | 通过 chub 检索版本化 API/SDK 文档与技能内容 | Claude / Codex |
| `google-workspace` | 只读访问 Gmail、Drive、Docs、Calendar 等 Google Workspace 能力 | Claude / Codex |
| `image-gen` | 图片生成与结构化图表生成 | Claude / Codex |
| `linuxdo` | 只读访问 LINUX DO 论坛 | Claude / Codex |
| `llm-wiki` | 用 analysis -> generation 维护 Karpathy 风格 markdown wiki，支持 ingest / query / lint | Claude / Codex |
| `midea-recall-diagnose-playwright` | keyword 漏召回排查、回放与 trace/ELK/ES 取证 | Claude / Codex |
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

- 日常共享 skill 同步默认由 AI 手工 diff 后执行最小落盘
- `./setup.sh` 仍可在 bootstrap / 灾备场景下把 `platforms/claude` 应用到 `~/.claude`
- 维护 `CLAUDE.md`、`skills/`、`agents/`、`hooks/`、`.mcp.json`、`.claude-plugin/`
- `.mcp.json` 模板内置 MCP：`playwright-ext`、`chrome-devtools`、`playwright`、`context7`、`tavily`
- 平台特有能力集中在 `cc-codex-review`、`plugin-manager`、`skill-creator`
- skill 级 `runtime.yaml` 仅保留在 repo 对应 skill 目录；平台级 `platforms/claude/runtime.yaml` 仅供仓库内 AI 理解迁移规则

### Codex

- 日常共享 skill 同步默认由 AI 手工 diff 后执行最小落盘
- `./scripts/sync_to_codex.sh` 仍可在 bootstrap / 灾备场景下同步 `platforms/codex` 到 `~/.codex`
- 受管 root 仅包含 `AGENTS.md`、`agents/`、`bin/`、`hooks/`、`scripts/`、`rules/`；`config.toml` 默认不覆盖本机
- `platforms/codex/config.toml` 模板内置浏览器 MCP：`playwright-ext` 与 `chrome-devtools`（需 `--sync-config` 才会应用）
- `--sync-config` 覆盖时会保留本机 MCP 敏感配置（鉴权字段、env token/key）
- `~/.codex/skills` 保留 `.system` 与本地未托管内容
- 平台特有能力集中在 `openai-docs`、`screenshot`
- skill 级 `runtime.yaml` 仅保留在 repo 对应 skill 目录；平台级 `platforms/codex/runtime.yaml` 仅供仓库内 AI 理解迁移规则

### Hermes

- `platforms/hermes/` 记录当前本机 `~/.hermes` 的目录布局、skill 映射关系与迁移基线
- `shared/skills/llm-wiki` 现已作为 repo-managed 真源；Hermes 本机 `llm-wiki` 应视为下游运行态副本，后续按人工审核做最小同步
- Hermes 当前不走仓库脚本同步；新机恢复采用“官方安装 + 手动放置同名 skill + 人工审核差异”的方式
- Hermes active skills 使用分类目录：`~/.hermes/skills/<category>/<skill>`
- 官方安装基线来自 `~/.hermes/hermes-agent`；仓库只记录值得保留的本机差异与已批准回流规则
- 同名 skill 回流仍按人工触发执行，先出差异总结，再决定是否回写仓库

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
- Hermes 当前使用态、迁移基线与差异说明：`platforms/hermes/README.md`
