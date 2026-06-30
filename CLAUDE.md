# CLAUDE.md

本文档用于指导 Claude Code 在本仓库内协作时的行为与约束。

## 项目概览

这是一个 `platform-first` 的多平台技能仓库：

- 不再以 `shared/skills/` 作为主要组织方式
- `platforms/claude`、`platforms/codex` 各自维护各自的平台真源
- 同名 skill 允许在不同平台目录重复存在

## 仓库结构

```text
all-my-ai-needs/
├── .claude-plugin/marketplace.json
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── PROFILES.md
└── platforms/
    ├── claude/
    │   ├── .claude-plugin/plugin.json
    │   ├── .mcp.json
    │   ├── runtime.yaml
    │   ├── skills.meta.yaml
    │   └── skills/
    └── codex/
        ├── config.toml
        ├── runtime.yaml
        ├── skills.meta.yaml
        └── skills/
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

同步方式：仓库不再提供同步脚本；由 AI agent 拉取仓库后，读取各平台 `runtime.yaml` / `skills.meta.yaml`，将 skill 真源手工 diff 后同步到对应运行目录（`~/.claude/skills`、`~/.codex/skills`），只落最小文件集。

运行目录规则：

- `runtime.yaml`、`skills.meta.yaml`、`PROFILES.md` 只保留在 repo，不下发到任何运行目录
- `agents`/`hooks`/`scripts`/`bin`、`config.toml` 等运行件由各设备本地自管，不入仓也不由仓库回写

## 提交前必检清单

当改动涉及 `platforms/` 下的文件时：

1. 由 AI 比对改动的 skill 真源与对应运行目录（`~/.claude/skills`、`~/.codex/skills`）的差异，确认一致
2. 同名 skill 多平台存在时，确认各平台语义仍符合各自约定
3. 推送前必须得到用户明确确认

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

## 安全基线

本仓库为公开仓库。Claude 处理同步、提交、生成 skill 或配置示例时，必须遵守根 `AGENTS.md` 的「公开仓库安全基线」与「提交前安全自查」：不提交真实身份、真实环境配置、内部服务信息或未参数化的个人路径；提交身份用 noreply；个人配置由各设备本地自管，不入仓。

## 通用约定

- 默认按平台目录维护，不把“抽象去重”当作首要目标
- 根 `README.md` 负责仓库级总览；平台 README 负责完整 skill 清单与同步说明
- skill 简介默认以 `SKILL.md` frontmatter 的 `description` 为准
- 提交信息遵循 Conventional Commits
- 每次提交信息正文必须包含 `[更新摘要]`
- 每次 `git commit` 后必须创建并推送 annotated tag，tag 注释也必须包含 `[更新摘要]`
