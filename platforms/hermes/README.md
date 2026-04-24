# Hermes 平台目录（hermes）

`platforms/hermes` 是当前 Hermes 平台的仓库真源，但只受管 local/DIY subset（`source=local`），不尝试镜像整份 `~/.hermes`。仓库采用 `platform-first`：Hermes 的 skill、cron 与迁移规则都留在 `platforms/hermes/` 下，和 Claude / Codex 分开维护。

## 当前定位

- 官方安装运行根目录：`~/.hermes`
- 官方源码/安装基线：`~/.hermes/hermes-agent`
- active skills 根目录：`~/.hermes/skills`
- active skills 原生布局：`~/.hermes/skills/<category>/<...>/<skill>`（允许多级分类）
- 仓库内 Hermes 真源：`platforms/hermes/skills/<category>/<...>/<skill>`、`platforms/hermes/cron/`、`platforms/hermes/config.template.yaml` 与 `platforms/hermes/memory/`

## 当前受管范围

当前仓库维护以下 Hermes 内容：

1. `hermes skills list --source local` 返回的 local/DIY skills
2. Hermes cron 相关内容
3. 脱敏配置模板：`platforms/hermes/config.template.yaml`（当前仅覆盖 `mcp_servers` 受管片段）
4. memory 白名单脱敏快照：`platforms/hermes/memory/{whitelist.yaml,redaction-rules.yaml,snapshots/*}`（仅 local->repo）

不纳入仓库的运行态内容：

- `~/.hermes/config.yaml`（运行态实值；仓库只保存脱敏模板）
- `~/.hermes/.env`
- `~/.hermes/.hub/`
- `~/.hermes/skill-promotions/`
- `~/.hermes/sessions/`、`~/.hermes/logs/`、`~/.hermes/memories/`（原始运行态文件）
- `~/.hermes/cron/output/`

## 当前 skill 清单（完整）

统计口径：

- 仓库 `platforms/hermes/skills` 当前 26 个 skill（完整清单如下）
- 本机 `hermes skills list --source local` 当前 24 个 skill
- 注意：`google-workspace`、`llm-wiki` 可能因 bundled manifest 命中显示为 `source=builtin`，但本机同名 local 路径仍可能存在

### autonomous-ai-agents

- `hermes-cron-local-script-notify`：本地脚本驱动的轻量 Hermes cron 与通知
- `hermes-skill-source-classification`：诊断 `source=builtin/local` 判定与误报
- `opencode-copilot-opus`：通过 opencode 与 GitHub Copilot Opus 持续协作讨论
- `skill-promotion-and-dedup`：将 imported skills 提升为一等分类并去重
- `trace-skill-provenance`：追溯 skill 来源、创建时间与归类路径

### creative

- `fireworks-tech-graph`：结构化技术图生成（架构图/流程图/时序图/泳道图，SVG+PNG）
- `ui-ux-pro-max`：UI/UX 设计知识与落地辅助

### mcp

- `context-hub`：通过 chub 访问版本化 API/SDK 文档与技能

### media

- `video-transcribe`：视频/音频转录、关键帧与可视分析

### note-taking

- `orbit-os`：OrbitOS Obsidian Vault 结构与规范
- `orbit-session-diary`：基于本地会话日志生成日记

### productivity

- `google-workspace`：Gmail/Calendar/Drive/Docs/Sheets 集成

### research

- `llm-wiki`：Karpathy 风格 markdown wiki 的 ingest/query/lint 工作流
- `openai-docs`：OpenAI 官方文档检索与实现指引
- `scrapling`：Scrapling 优先的网页抓取与结构化提取

### social-media

- `bird-twitter`：默认 X/Twitter 只读流程
- `linuxdo`：LINUX DO 论坛只读访问
- `reddit`：Reddit 只读访问
- `x-article-canonicalization`：X 长文高保真 canonical 落库
- `xiaohongshu-session-reader`：小红书 HTTP/API 优先读取，必要时回退 Playwright

### software-development

- `midea-recall-diagnose-playwright`：`/rag-recall/api/search/keyword` 漏召回排障与取证
- `peekaboo`：macOS 截图与视觉分析
- `pinchtab`：PinchTab 优先浏览器自动化
- `playwright`：MCP-only 真实浏览器自动化
- `repo-hermes-config-template-sync`：Hermes 脱敏配置模板与同步脚本落库流程
- `screenshot`：系统级截图与区域捕获

## 仓库目录布局

```text
platforms/hermes/
├── README.md
├── runtime.yaml
├── config.template.yaml
├── memory/
│   ├── README.md
│   ├── whitelist.yaml
│   ├── redaction-rules.yaml
│   └── snapshots/
├── scripts/
│   └── managed_skills.sh
├── skills/
│   └── <category>/<skill>/
└── cron/
    ├── jobs.json
    └── scripts/
        └── codex_keepalive_notify.py
```

## 受管 skill 判定规则

- 不再按 Codex 同名推导，不再使用 `managed-extra-skills.txt`。
- 默认规则：仅以 `hermes skills list --source local` 作为受管集合来源。
- 官方来源索引优先按 `hermes skills list --source builtin|hub` 读取；若 builtin 查询失败则回退 `~/.hermes/skills/.bundled_manifest`。
- `managed_skills.sh` 会基于 local 列表中的 `name/category` 回查 `~/.hermes/skills/**/SKILL.md`，解析真实路径后再比较（支持 `mlops/models/*` 这类多级分类）。
- `candidates` 默认只自动排除 `upstream-mirror`；其余分类（含 `upstream-catalog` / `upstream-superseded`）都会保留在候选中做人审，避免同名目录误杀。
  - `upstream-mirror`：与 upstream（`~/.hermes/hermes-agent/{skills,optional-skills}`）目录内容一致。
  - `upstream-catalog`：未在本机 upstream 目录找到同名副本，但 `SKILL.md` 作者为 `Orchestra Research`（通常属于上游目录重组或导入形态）。
  - `upstream-superseded`：本机仍保留旧 skill，但 upstream 已由新 skill 显式 supersede/replace（例如 `find-nearby`、`xitter`）。
- `repo - local` 会先区分“本地磁盘缺失”与“本地存在但非 `source=local`”，仅前者标记为删除候选；删除必须人工确认。

推荐直接用检查脚本：

```bash
./scripts/syncctl.sh check --direction repo-to-local --platform hermes --scope all
./scripts/syncctl.sh apply --plan-id <plan_id> --approve-token <token>
bash platforms/hermes/scripts/managed_skills.sh list
bash platforms/hermes/scripts/managed_skills.sh status
bash platforms/hermes/scripts/managed_skills.sh candidates
bash platforms/hermes/scripts/managed_skills.sh likely-custom
bash platforms/hermes/scripts/managed_skills.sh official-review
bash platforms/hermes/scripts/managed_skills.sh unmanaged-repo
```

输出含义：

- `syncctl check/apply`：统一入口，按 Hermes 受管边界（`source=local` + `cron` + `memory` 白名单脱敏快照）生成并执行计划
- `list`：列出当前本机 local skills（`source=local`），并附 provenance 分类与 `official_hint`（`official-confirmed-builtin` / `official-confirmed-hub` / `official-likely-upstream` / `likely-custom` / `review`）
- `status`：列出 local skills、repo 与 local 交集 diff、待新增候选（已排除 `upstream-mirror`）、`likely-custom` 子集、`official-review` 子集、被排除项、以及 repo 侧两类差异：
  - 本地已存在但不在 `source=local`（通常是 builtin/hub）
  - 本地磁盘缺失（才作为删除候选）
- `candidates`：只列出待补回仓候选（默认排除 `upstream-mirror`）
- `likely-custom`：只列出更可能是自定义回流项（`custom-local` + `upstream-variant`）
- `official-review`：列出带官方迹象的待审项（`upstream-superseded` / `upstream-catalog` / `unknown`）
- `unmanaged-repo`：只列出“本地磁盘缺失”的待删除候选（仅供人工确认）

## Cron 受管内容

当前仓库已记录：

- `platforms/hermes/cron/jobs.json`
- `platforms/hermes/cron/scripts/codex_keepalive_notify.py`

说明：

- `jobs.json` 是当前已批准入仓的 cron 配置快照
- `cron/output/`、锁文件与运行日志不入仓
- 若 cron 继续扩展，优先把“配置 + 脚本”纳入仓库，而不是把运行结果目录纳入仓库

## 配置模板（脱敏）与手动合并

当前仓库新增：`platforms/hermes/config.template.yaml`。

- 只保存受管片段（当前为 `mcp_servers`），不保存运行态私密实值
- 占位符写法统一为 `<...>`，例如 `<PLAYWRIGHT_EXT_TOKEN>`
- 合并入口：`./scripts/sync_to_hermes.sh`

推荐命令：

```bash
./scripts/sync_to_hermes.sh --dry-run
./scripts/sync_to_hermes.sh --sync-config
```

合并策略：

- 非占位模板值会更新到本机 `~/.hermes/config.yaml`
- 占位模板值优先保留本机已有非占位值
- 若本机缺失且存在同名环境变量，则使用环境变量值
- 不改动 skills/cron 的手工同步策略

## Memory 白名单脱敏快照（local->repo）

当前仓库新增：`platforms/hermes/memory/{whitelist.yaml,redaction-rules.yaml,snapshots/}`。

- `~/.hermes/memories/` 原始运行态文件不入仓
- 仅白名单条目会生成脱敏快照到 `platforms/hermes/memory/snapshots/`
- 仅支持 `local->repo`，不支持 `repo->local` 回写 memory
- check 与 apply 两阶段审批，apply 前必须人工确认

推荐命令：

```bash
./scripts/sync_hermes_memory_whitelist.sh check
./scripts/sync_hermes_memory_whitelist.sh apply --plan-id <plan_id> --approve-token <token>
```

## 日常同步规则

- Hermes skills/cron 不走自动镜像脚本
- 配置模板合并仅允许用户手动触发 `./scripts/sync_to_hermes.sh`
- memory 回流仅允许用户手动触发 `./scripts/sync_hermes_memory_whitelist.sh` 或 `syncctl --scope memory`
- 仅当用户手动触发时，比较 `source=local` 集合与仓库同名路径
- 同步前必须先给出差异总结
- 同步后必须明确汇报：新增、更新、删除、跳过或未同步项

## 新机迁移

建议按下面顺序恢复：

1. 先按 Hermes 官方方式安装，确认 `~/.hermes/hermes-agent`、`~/.hermes/config.yaml`、`hermes` 命令可用。
2. 先恢复个人私有配置：`~/.hermes/config.yaml`、`~/.hermes/.env`、必要登录态与 OAuth 文件；这些实值不入仓。
3. 用 `./scripts/sync_to_hermes.sh --dry-run` 预览模板差异，确认后再执行 `--sync-config` 合并受管配置片段。
4. 按本目录中的 `skills/`、`cron/`、`memory/` 恢复受管内容（memory 仅恢复白名单与规则，不回写原始 memory）。
5. 不要迁移 `.hub/`、`skill-promotions/`、`sessions/`、`logs/`、`memories/`（原始运行态）、`cron/output/`。
6. 若之后需要把 Hermes 新变化回写仓库，先运行 `bash platforms/hermes/scripts/managed_skills.sh status`（skills）或 `./scripts/sync_hermes_memory_whitelist.sh check`（memory），再先输出差异总结给用户审核。

## 校验命令

```bash
hermes skills list --source local
bash platforms/hermes/scripts/managed_skills.sh status
./scripts/sync_to_hermes.sh --dry-run
./scripts/sync_hermes_memory_whitelist.sh check
./scripts/syncctl.sh check --direction local-to-repo --platform hermes --scope memory
hermes mcp list
hermes mcp test playwright-ext
find ~/.hermes/skills -mindepth 2 -maxdepth 4 -type d | sort
cat ~/.hermes/cron/jobs.json
```
