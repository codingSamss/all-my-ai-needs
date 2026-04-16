# CLAUDE.md

本文档用于指导 Claude Code 在本仓库内协作时的行为与约束。

## 项目概览

这是一个 `platform-first` 的多平台技能仓库：

- 不再以 `shared/skills/` 作为主要组织方式
- `platforms/claude`、`platforms/codex`、`platforms/hermes` 各自维护各自的平台真源
- 同名 skill 允许在不同平台目录重复存在
- Hermes 仅受管 local/DIY subset（`source=local`），不尝试镜像整份 `~/.hermes`

## 仓库结构

```text
all-my-ai-needs/
├── .claude-plugin/marketplace.json
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── setup.sh
├── scripts/
└── platforms/
    ├── claude/
    │   ├── CLAUDE.md
    │   ├── .claude-plugin/plugin.json
    │   ├── .mcp.json
    │   ├── runtime.yaml
    │   ├── skills/
    │   ├── hooks/
    │   └── agents/
    ├── codex/
    │   ├── AGENTS.md
    │   ├── config.toml
    │   ├── runtime.yaml
    │   ├── skills/
    │   ├── hooks/
    │   ├── agents/
    │   ├── bin/
    │   ├── rules/
    │   └── scripts/
    └── hermes/
        ├── README.md
        ├── runtime.yaml
        ├── skills/
        │   └── <category>/<skill>/
        └── cron/
```

## Skill 文件格式

每个 skill 通过 `SKILL.md` 定义。推荐结构：

```markdown
---
name: skill-name
description: "包含触发关键词的描述"
---

# Skill 标题

给 agent 的执行指令...
```

- `name` 与 `description` 决定发现与触发行为
- `description` 建议包含中英文关键词
- `runtime.yaml` 是 repo 内治理元数据，不下发到运行目录

## 本地同步规则

本项目按平台同步生效。GitHub 仓库、本地工作区与相关本地运行目录必须保持一致。

同步入口：

- Claude：`./setup.sh`，主要用于 bootstrap / 灾备；日常优先手工 diff
- Codex：`./scripts/sync_to_codex.sh`，主要用于 bootstrap / 灾备；日常优先手工 diff
- Hermes：没有自动同步脚本；仅对 local/DIY subset（`source=local`）做人工 diff + 最小落盘

运行目录规则：

- `runtime.yaml` 只保留在 repo，不下发到任何运行目录
- `agents/openai.yaml` 仅在 Codex / OpenAI 风格运行目录确有必要时才保留
- Hermes 运行目录优先保留原生最小集；仓库中允许保留额外治理元数据

## 提交前必检清单

当改动涉及 `platforms/` 下的文件时，禁止直接跳过平台同步检查：

1. 涉及 `platforms/claude/` 的改动：先执行 `./setup.sh <skill>` 或 `./setup.sh core`
2. 涉及 `platforms/codex/` 的改动：先执行 `./scripts/sync_to_codex.sh --dry-run`
3. 涉及 `platforms/hermes/` 的改动：先比较仓库 local/DIY 受管目录与 `~/.hermes` 中 `source=local` 的同名目录差异，再给出差异总结
4. 推送前必须得到用户明确确认

## 隐私与一致性检查

在执行 `git commit` 前，至少完成以下检查：

1. 隐私扫描：
   - `git grep -nEI "AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|PLAYWRIGHT_MCP_EXTENSION_TOKEN\\s*=\\s*\"[^<\\\"]+\"|x-api-key\\s*[:=]\\s*\"[^<\\\"]+\""`
2. 完整性检查：
   - `git diff --check && git diff --cached --check`
3. 删除引用检查：
   - `git grep -nE "playwright/scripts/playwright_cli\\.sh|playwright/references/cli\\.md|playwright/references/workflows\\.md|\\$PWCLI\\b|@playwright/cli\\b" || true`
4. 平台一致性检查：
   - 同名 skill 若在多个平台都存在，必须确认语义是否仍然符合各自平台约定

## 通用约定

- 默认按平台目录维护，不把“抽象去重”当作首要目标
- 根 `README.md` 负责仓库级总览；平台 README 负责完整 skill 清单与同步说明
- skill 简介默认以 `SKILL.md` frontmatter 的 `description` 为准
- `scripts/` 下脚本应可重复执行、无副作用残留
- 提交信息遵循 Conventional Commits
- 每次提交信息正文必须包含 `[更新摘要]`
- 每次 `git commit` 后必须创建并推送 annotated tag，tag 注释也必须包含 `[更新摘要]`
