# CLAUDE.md

本文档用于指导 Claude Code（claude.ai/code）在本仓库内协作时的行为与约束。

## 项目概览

这是一个多平台技能仓库，以平台隔离为主，并允许少量经批准的共享 skill 真源。仓库包含技能、脚本、Hook 与 Agent 配置。

## 仓库结构

```text
all-my-ai-needs/
├── shared/skills/                    # 经批准的共享 skill 真源（当前如 llm-wiki）
├── .claude-plugin/marketplace.json   # 插件注册信息
├── AGENTS.md                         # 仓库级协作约束
├── CLAUDE.md                         # 仓库级 Claude 协作约束
├── README.md                         # 仓库级能力总览
├── setup.sh                          # Claude 平台配置入口
├── scripts/                          # 同步/引导脚本
└── platforms/
    ├── claude/                       # Claude 唯一真源
    │   ├── CLAUDE.md
    │   ├── .claude-plugin/plugin.json
    │   ├── .mcp.json
    │   ├── runtime.yaml
    │   ├── skills/
    │   ├── hooks/
    │   └── agents/
    └── codex/                        # Codex 平台专属真源
        ├── AGENTS.md
        ├── config.toml
        ├── runtime.yaml
        ├── skills/
        ├── hooks/
        ├── agents/
        ├── bin/
        ├── rules/
        └── scripts/
```

## Skill 文件格式

每个技能通过 `SKILL.md` 定义，推荐结构如下：

```markdown
---
name: skill-name
description: "包含触发关键词的描述"
---

# Skill 标题

给 Claude 的执行指令...
```

- YAML 头中的 `name` 与 `description` 决定发现与触发行为。
- `description` 建议包含中英文关键词，便于搜索命中。
- Markdown 正文为完整执行指令。
- 参数约定：`$ARGUMENTS`（全部参数）、`$1`/`$2`（位置参数）。

## 典型技能与依赖

这里只列容易踩坑或依赖明显的典型技能；完整 skill 清单以根 `README.md` 与平台 README 为准。

| 技能 | 外部依赖 | 运行时 |
|---|---|---|
| bird-twitter | Bird CLI（`brew install steipete/tap/bird`） | - |
| peekaboo | Peekaboo（`brew install steipete/tap/peekaboo`） | - |
| cc-codex-review | Codex MCP 服务 | Python（`scripts/topic-manager.py`） |
| plugin-manager | Claude Code 插件系统 | Bash（`scripts/`） |
| ui-ux-pro-max | Python 3 | Python（`scripts/search.py`、`scripts/core.py`） |
| video-transcribe | yt-dlp、ffmpeg、Groq API Key | Bash + curl |

## 架构约定

- 技能目录隔离：每个技能在 `skills/<skill-name>/` 独立维护，避免跨技能耦合。
- 脚本委派：复杂技能通过入口脚本分派到子脚本，不在提示词中堆积逻辑。
- 数据驱动（ui-ux-pro-max）：使用 CSV 作为知识库，结合 BM25（`core.py`）由 `search.py` 查询。

## 本地同步规则

本项目按平台同步生效。GitHub 仓库、本地项目目录、共享 skill 真源目录与本地 CLI 根目录（`~/.claude`、`~/.codex`）必须保持一致。

同步入口：
- Claude：日常共享 skill 同步默认由 AI 手工 diff 后最小落盘；`./setup.sh` 仅作 bootstrap / 灾备 fallback（可指定 skill：`./setup.sh <skill>`）
- Codex：日常共享 skill 同步默认由 AI 手工 diff 后最小落盘；`./scripts/sync_to_codex.sh` 仅作 bootstrap / 灾备 fallback
- Codex root 受管配置：`platforms/codex/{AGENTS.md,config.toml,agents,bin,hooks,scripts,rules}` 同步到 `~/.codex/...`

共享 skill 运行目录规则：
- `runtime.yaml` 只保留在 repo，不下发到任何运行目录
- `agents/openai.yaml` 仅在 Codex / OpenAI 风格运行目录确有必要时才下发
- Hermes 默认只保留 `SKILL.md` 与必要的 `metadata.hermes.config`

### 提交前必检清单

当改动涉及 `platforms/` 或 `shared/skills/` 下的文件时，**禁止直接 git commit**，必须按以下顺序操作：

1. 涉及 `platforms/claude/` 的改动 -> 先执行 `./setup.sh <skill>` 或 `./setup.sh`，确认同步成功
2. 涉及 `platforms/codex/` 的改动 -> 先执行 `./scripts/sync_to_codex.sh`，确认同步成功
3. 两个平台都涉及时，两个同步脚本都要执行
4. 同步全部通过后，再执行 git commit + push（push 需用户明确确认）

**注意**：
- 用户要求 commit 或 push 时，如果本次改动涉及 `platforms/` 目录，必须先触发上述同步流程，不可跳过。
- 用户要求“同步仓库内容”“提交”或“推送”时，先比较本地 `~/.codex`、`~/.claude` 与仓库受管全局配置；忽略 secrets、占位符和运行态噪音，若本地有值得保留的新内容，先提示同步回仓库，再继续。
- 当新增、删除、重命名 skill，修改 `SKILL.md` 的 `description` 或平台归属，调整平台能力资产、同步入口、用户可见行为时，必须检查根 `README.md` 与受影响平台 README 是否需要同步更新。

### 提交前隐私与一致性检查（必做）

在执行 `git commit` 前，必须完成以下检查并确认结果：

1. 隐私扫描（仅允许占位符，不允许真实凭据）：
   - `git grep -nEI "AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|PLAYWRIGHT_MCP_EXTENSION_TOKEN\\s*=\\s*\"[^<\\\"]+\"|x-api-key\\s*[:=]\\s*\"[^<\\\"]+\""`
2. 完整性检查（避免坏 diff）：
   - `git diff --check && git diff --cached --check`
3. 删除引用检查（删除文件后不得残留引用）：
   - `git grep -nE "playwright/scripts/playwright_cli\\.sh|playwright/references/cli\\.md|playwright/references/workflows\\.md|\\$PWCLI\\b|@playwright/cli\\b" || true`
4. 平台一致性检查（涉及同名 skill 的双端改动时必须做）：
   - 对比 `platforms/claude/skills/<skill>` 与 `platforms/codex/skills/<skill>`，仅允许平台路径差异（如 `~/.claude` vs `~/.codex`），命令语义必须一致。

若发现疑似隐私泄漏：
- 立即停止提交与推送；
- 先替换为占位符并轮换密钥；
- 若已推送历史包含泄漏，必须执行历史清理（`git filter-repo`/BFG）并强推，同时通知所有协作者重新同步。

## 通用约定

- 技能描述建议包含中英文触发词。
- 每个技能目录建议包含 `SKILL.md`、`runtime.yaml`；如有确定性脚本或检查，再补 `README.md`、`setup.sh`。
- 根 `README.md` 负责仓库级能力总览；`platforms/{claude,codex}/README.md` 负责对应平台的完整 skill 清单与同步说明。
- skill 简介默认以对应 `SKILL.md` frontmatter 的 `description` 为准；README 只做压缩，不另写脱离源文案。
- `scripts/` 下脚本应保持可执行、可重复运行、无副作用残留。
- 提交信息遵循 Conventional Commits（如 `feat:`、`fix:`、`chore:`）。
- 每次提交信息正文必须包含 `[更新摘要]` 标签，并在其下使用中文分点列出本次改动（建议 2-5 条，每条一句）。
- 每次 `git commit` 后必须创建并推送一个 Git annotated tag，且 tag 注释中也必须包含 `[更新摘要]` 与中文分点总结。
- 推荐 tag 命名：`sync-YYYYMMDD-<short-topic>` 或 `feat-YYYYMMDD-<short-topic>`（短主题使用小写短横线）。
- 提交摘要格式示例：
  - `[更新摘要]`
  - `- 新增 ...`
  - `- 调整 ...`
  - `- 修复 ...`
  - `git tag -a sync-20260314-mcp-template -m "[更新摘要]" -m "- 新增 ..." -m "- 调整 ..."`
