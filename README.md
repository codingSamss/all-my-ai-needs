# all-my-ai-needs

> 跨 Claude Code 与 Codex 两套 agent 的能力真源：skills、agents、hooks 与同步规则。写入由 agent 执行，人只审校与决策。

把 Claude Code 与 Codex 的可复用能力收敛到一个仓库，按 `platform-first` 维护：每个平台独立持有自己的 `skills/`、`agents/`、`hooks/` 与运行约定，同名 skill 允许在两端并存，不强行抽象去重。

仓库要解决的是多端 AI 配置的漂移——GitHub 仓库、本地工作区、本地 CLI 运行目录（`~/.claude`、`~/.codex`）三者保持一致。所有写入（同步、提交、推送）由 agent 执行，人负责审校差异与最终决策；脚本只承担确定性的只读校验与灾备重建。

## 仓库结构

```text
all-my-ai-needs/
├── README.md                       # 仓库总览(本文件)
├── CLAUDE.md / AGENTS.md           # Claude / Codex 协作规范
├── PROFILES.md                     # skill 同步分层(scope / profile)
├── setup.sh                        # Claude bootstrap / 灾备安装器
├── .claude-plugin/marketplace.json
├── scripts/
│   ├── syncctl.sh                  # 统一同步入口(check / apply 两阶段审批)
│   ├── sync_to_codex.sh            # Codex bootstrap / 灾备
│   ├── bootstrap.sh                # 新机一键
│   ├── skills_meta_audit.sh        # 只读：校验 manifest 与目录一致
│   └── lib/
└── platforms/
    ├── claude/                     # Claude 平台真源 → ~/.claude
    │   ├── README.md  CLAUDE.md  runtime.yaml  .mcp.json
    │   ├── skills.meta.yaml         # repo-only 同步分层真源
    │   ├── skills/ (21)  agents/  hooks/
    │   └── .claude-plugin/plugin.json
    └── codex/                      # Codex 平台真源 → ~/.codex
        ├── README.md  AGENTS.md  runtime.yaml  config.toml
        ├── skills.meta.yaml         # repo-only 同步分层真源
        └── skills/ (21)  agents/  bin/  hooks/  rules/  scripts/
```

## 核心模型

1. **platform-first** —— `platforms/claude/`、`platforms/codex/` 各为真源，互不依赖；不设跨平台共享 skill 目录，同名 skill 按各自平台约定演化。
2. **agent 写入 · 人审校** —— 仓库内容默认由 agent 维护。涉及写入的操作先产出只读差异清单交人审批再执行；脚本只做万无一失的事（只读校验、bootstrap / 灾备）。
3. **scope / profile 分层** —— 每个 skill 标注 `scope`（core / project / manual-only）与项目类型 `profile`，决定何时下发到运行目录。机读真源是各平台 `skills.meta.yaml`，人读视图与同步剧本见 [PROFILES.md](PROFILES.md)。

## 能力地图

按能力域分组；完整 per-skill 能力与运行依赖见各平台 README。

| 能力域 | Skills |
| --- | --- |
| 常驻 `core` | `git-ops` `handoff` `teach`；Claude 另含 `cc-codex-review` `skill-creator` |
| 知识库 `obsidian-kb` | `orbit-os` `orbit-session-diary` `official-article-ingest` `online-doc-html` `video-transcribe` |
| 前端设计 `frontend-design` | `gsap` `fireworks-tech-graph` `ian-xiaohei-illustrations`；Codex 另含 `taste-design` |
| 社交只读 `social-reading` | `bilibili` `bird-twitter` `reddit` `linuxdo` `xiaohongshu` |
| 浏览器自动化 `web-automation` | `playwright` `screenshot` |
| macOS 维护 `macos-local` | `mole-mac-cleanup` `screenshot` |
| 点名 `manual-only` | `openai-docs`（Codex） |

## 同步模型

日常同步由 agent 驱动，围绕只读检查 + 人工审批：

```bash
# 1) 只读出差异计划
./scripts/syncctl.sh check --direction repo-to-local --platform codex --scope skills --skill <name>
# 2) 人审通过后，凭 plan_id + approve_token 执行
./scripts/syncctl.sh apply --plan-id <plan_id> --approve-token <token>
```

`setup.sh`、`scripts/sync_to_codex.sh`、`scripts/bootstrap.sh` 是全量镜像入口，仅用于新机初始化与灾备重建，不用于日常增量同步。

下发禁区（任何方向都遵守）：

- `runtime.yaml`、`skills.meta.yaml`、`PROFILES.md` 等治理元数据只留在仓库，不进入 `~/.claude`、`~/.codex`。
- 本地 repo 之外的私有 skill（如 `mx-*`、`midea-*`）与含内网信息的配置不回流仓库，也不被同步删除。

## 治理与约定

- 协作规范：[CLAUDE.md](CLAUDE.md)（Claude Code）、[AGENTS.md](AGENTS.md)（Codex / 通用 agent）。
- 同步分层：[PROFILES.md](PROFILES.md)；改动 skill 后运行 `bash scripts/skills_meta_audit.sh` 校验 manifest 与目录一致。
- 提交门禁：推送前必过隐私扫描与 `git diff --check`；提交信息遵循 Conventional Commits 且含 `[更新摘要]`，提交后打 annotated tag。细则见 [AGENTS.md](AGENTS.md)。

## 平台文档

- Claude 完整 skill 清单与同步说明：[platforms/claude/README.md](platforms/claude/README.md)
- Codex 完整 skill 清单与同步说明：[platforms/codex/README.md](platforms/codex/README.md)
