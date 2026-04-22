# All My AI Needs（Claude Code + Codex + Hermes）

这个仓库采用 `platform-first` 维护模式：每个平台各自维护自己的 `skills/`、脚本与运行约定；允许同名 skill 在不同平台目录中并存，不强行去重。当前 Hermes 也已经纳入仓库，但只受管 local/DIY subset（`source=local`），而不是整份 `~/.hermes`。

- Claude 平台真源：`platforms/claude/`
- Codex 平台真源：`platforms/codex/`
- Hermes 平台真源：`platforms/hermes/`
- 根脚本入口：`./setup.sh`、`./scripts/syncctl.sh`、`./scripts/sync_to_codex.sh`、`./scripts/sync_to_hermes.sh`、`./scripts/bootstrap.sh`
- skill 简介以对应 `SKILL.md` 的 `description` 为准；根 README 负责仓库级总览，平台 README 负责各平台完整清单

默认同步策略：
- 日常同步优先由 AI 做“人工 diff + 最小落盘”，不直接依赖脚本镜像。
- 日常一致性检查优先使用 `./scripts/syncctl.sh check`，执行同步使用 `plan_id + approve_token` 的两阶段 `apply`。
- `runtime.yaml` 只保留在 repo，不下发到 `~/.claude`、`~/.codex`、`~/.hermes`。
- `./setup.sh`、`./scripts/sync_to_codex.sh`、`./scripts/sync_to_hermes.sh`、`./scripts/bootstrap.sh` 主要用于新机初始化、灾备恢复、整个平台重建。
- Hermes 的 skills/cron 仍以人工 diff 同步为主；仅提供 `./scripts/sync_to_hermes.sh` 做“脱敏配置模板 -> 本机 config”手动合并。

## 当前 Skills 总览

### Claude / Codex / Hermes

| Skill | 能力 |
| --- | --- |
| `bird-twitter` | 只读访问 X/Twitter 内容 |
| `context-hub` | 通过 chub 检索版本化 API/SDK 文档与技能内容 |
| `google-workspace` | 访问 Gmail、Drive、Docs、Calendar 等 Google Workspace 能力 |
| `image-gen` | 图片生成与结构化图表生成 |
| `fireworks-tech-graph` | 结构化技术图生成（架构图/流程图/时序图/泳道图，SVG+PNG） |
| `linuxdo` | 只读访问 LINUX DO 论坛 |
| `llm-wiki` | 用 analysis -> generation 维护 Karpathy 风格 markdown wiki，支持 ingest / query / lint |
| `midea-recall-diagnose-playwright` | keyword 漏召回排查、回放与 trace/ELK/ES 取证 |
| `orbit-os` | OrbitOS Obsidian Vault 共享配置与规范 |
| `orbit-session-diary` | 基于本地会话日志生成 Obsidian 日记 |
| `peekaboo` | macOS 截图与视觉分析 |
| `pinchtab` | PinchTab 优先的浏览器自动化，失败时回退 `playwright-ext` |
| `playwright` | MCP-only 真实浏览器自动化 |
| `reddit` | 只读访问 Reddit 内容 |
| `scrapling` | Scrapling 优先的网页抓取与结构化提取 |
| `ui-ux-pro-max` | UI/UX 设计知识检索与落地辅助 |
| `video-transcribe` | 视频/音频转录、关键帧分析与总结 |
| `xiaohongshu-session-reader` | 小红书 HTTP/API 优先读取，必要时回退 Playwright |

### Codex / Hermes

| Skill | 能力 |
| --- | --- |
| `openai-docs` | OpenAI 官方文档与 API 实现指引 |
| `opencode-copilot-opus` | 通过 opencode 与 GitHub Copilot Opus 持续协作讨论 |
| `screenshot` | 系统级截图与区域捕获 |

### Claude-only

| Skill | 能力 |
| --- | --- |
| `cc-codex-review` | Claude / Codex 协作讨论与 Battle Loop |
| `plugin-manager` | Claude Code 插件管理 |
| `skill-creator` | 创建、优化、评估 skills |

### Hermes-only

| Skill | 能力 |
| --- | --- |
| `hermes-cron-local-script-notify` | 创建轻量 Hermes cron job，让真正工作在本地脚本中执行并发送 macOS 通知 |
| `hermes-skill-source-classification` | 诊断 Hermes `source=builtin/local` 判定与误报，避免错误同步决策 |
| `repo-hermes-config-template-sync` | 将 Hermes 脱敏配置模板与 `sync_to_hermes.sh` 同步流程沉淀到仓库 |
| `skill-promotion-and-dedup` | 将 imported skills 提升为一等分类并去重，保留回滚路径 |
| `trace-skill-provenance` | 追溯 skill 来源、创建时间、builtin/local 归属与修改会话线索 |
| `x-article-canonicalization` | 将 X/Twitter 长文高保真落库到 Obsidian/知识库（block 顺序、可点击链接、图片本地化） |

## 平台能力摘要

### Claude

- 真源目录：`platforms/claude/`
- `./setup.sh` 用于 bootstrap / 灾备场景，把 `platforms/claude` 应用到 `~/.claude`
- 维护 `CLAUDE.md`、`skills/`、`agents/`、`hooks/`、`.mcp.json`、`.claude-plugin/`
- `.mcp.json` 模板内置 MCP：`playwright-ext`、`chrome-devtools`、`playwright`、`context7`、`tavily`

### Codex

- 真源目录：`platforms/codex/`
- `./scripts/sync_to_codex.sh` 用于 bootstrap / 灾备场景，把 `platforms/codex` 应用到 `~/.codex`
- 受管 root 仅包含 `AGENTS.md`、`agents/`、`bin/`、`hooks/`、`scripts/`、`rules/`
- `platforms/codex/config.toml` 默认不自动覆盖本机，仅在显式 `--sync-config` 时同步

### Hermes

- 真源目录：`platforms/hermes/`
- `platforms/hermes/skills/` 保持 Hermes 原生分类布局：`<category>/<skill>`
- 当前只受管 local/DIY subset：
  - 仅纳入 `hermes skills list --source local` 的 skill
  - 不纳入 builtin / hub
  - Hermes cron 相关内容
  - 脱敏配置模板 `platforms/hermes/config.template.yaml`（当前覆盖 MCP 片段）
- `platforms/hermes/cron/` 当前保存 `jobs.json` 与依赖脚本
- `bash platforms/hermes/scripts/managed_skills.sh status` 可查看当前受管集合、diff 与待补回仓候选
- `./scripts/sync_to_hermes.sh --dry-run` 预览配置模板合并，`--sync-config` 执行写入（保留本机非占位敏感值）
- Hermes skills/cron 仍不走自动镜像脚本；新机恢复采用“官方安装 + 手工放置 local/DIY skills + 人工审核差异”的方式

## 快速入口

### 统一检查/执行入口（推荐）

```bash
./scripts/syncctl.sh check --direction repo-to-local --platform codex --scope skills --skill fireworks-tech-graph
./scripts/syncctl.sh apply --plan-id <plan_id> --approve-token <token>
```

### Claude

```bash
./setup.sh
./setup.sh list
./setup.sh llm-wiki
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

### Hermes（配置模板）

```bash
./scripts/sync_to_hermes.sh --dry-run
./scripts/sync_to_hermes.sh --sync-config
```

### 新机一键

```bash
./scripts/bootstrap.sh all
```

## 文档入口

- Claude 平台完整能力与同步说明：`platforms/claude/README.md`
- Codex 平台完整能力与同步说明：`platforms/codex/README.md`
- Hermes local/DIY subset、cron 与迁移说明：`platforms/hermes/README.md`
