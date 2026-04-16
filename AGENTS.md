# Repository Guidelines

## 项目结构与模块组织

本仓库采用 `platform-first` 模型：`platforms/claude/`、`platforms/codex/`、`platforms/hermes/` 各自维护各自的平台真源；允许同名 skill 在不同平台目录并存，不强行去重。`shared/` 不再作为主要组织方式。

- `platforms/claude/`：Claude 的 `skills/`、`agents/`、`hooks/`、`.claude-plugin/` 与安装脚本。
- `platforms/codex/`：Codex 的 `skills/`、`agents/`、`hooks/`、`scripts/`、`rules/`、`bin/`。
- `platforms/hermes/`：Hermes 的 local/DIY subset；包含 `skills/`、`cron/` 与脱敏配置模板 `config.template.yaml`。其中 `skills/` 保持 Hermes 原生分类布局：`<category>/<skill>`。
- 根脚本：`setup.sh`、`scripts/bootstrap.sh`、`scripts/sync_to_codex.sh`、`scripts/sync_to_hermes.sh`。
- 平台级迁移说明：`platforms/{claude,codex,hermes}/runtime.yaml`。
- `runtime.yaml` 的字段约定以各平台 `skill_runtime_contract` 为准；平台固定为各自目录对应平台，不再使用 `platform: shared`。

每个技能目录建议包含 `SKILL.md`、`runtime.yaml`；如有确定性脚本或检查，再补 `README.md`、`setup.sh`。其中 Codex 技能必须有 `SKILL.md`。

## 平台同步策略

- 日常同步默认采用“AI 人工同步 + 差异审阅”，不是直接跑脚本做目录镜像。
- `setup.sh`、`scripts/sync_to_codex.sh`、`scripts/bootstrap.sh` 仅用于新机初始化、灾备恢复、整个平台重建；`scripts/sync_to_hermes.sh` 仅用于手动合并 Hermes 脱敏配置模板。
- `runtime.yaml` 必须留在 repo，**不得**下发到 `~/.claude/skills`、`~/.codex/skills`、`~/.hermes/skills`。
- `agents/openai.yaml` 仅在 Codex / OpenAI 风格运行目录确有必要时才下发；Claude 与 Hermes 默认不带。
- Hermes 受管范围：`source=local` skills + cron + 脱敏配置模板；运行态实值配置（`~/.hermes/config.yaml`、`~/.hermes/.env`）不入仓。
- 当用户要求“同步某个 skill”时，先比较该平台目录与对应本地运行目录的差异，再执行最小同步并回报结果；不要顺手同步无关 skill。

## README 维护约定

- 根 `README.md` 负责仓库级能力总览：平台模型、技能概览、平台摘要、同步入口。
- `platforms/{claude,codex,hermes}/README.md` 负责对应平台的完整 skill 清单、平台能力资产与同步说明。
- skill 简介默认以对应 `SKILL.md` frontmatter 的 `description` 为准；README 只做压缩，不另写脱离源文案。
- 当新增、删除、重命名 skill，修改 `SKILL.md` 的 `description` 或平台归属，调整平台能力资产、同步入口、用户可见行为时，提交或推送前必须检查并同步更新相关 README。

## 构建、测试与开发命令

- `./setup.sh list`：列出 Claude 平台可执行配置的技能。
- `./setup.sh all`：执行 Claude 的核心配置与全部技能配置（bootstrap / 灾备 fallback）。
- `./setup.sh <skill...>`：仅配置指定 Claude 技能。
- `./scripts/sync_to_codex.sh --dry-run`：预览 Codex 配置同步结果。
- `./scripts/sync_to_codex.sh`：同步 `platforms/codex/skills` 与受管 root 配置到 `~/.codex`（bootstrap / 灾备 fallback，默认不覆盖本机 `config.toml`）。
- `./scripts/sync_to_codex.sh --sync-config`：显式同步 `platforms/codex/config.toml` 到 `~/.codex/config.toml`。
- `./scripts/sync_to_hermes.sh --dry-run`：预览 Hermes 脱敏配置模板与本机 `~/.hermes/config.yaml` 的受管片段合并结果。
- `./scripts/sync_to_hermes.sh --sync-config`：手动合并 Hermes 脱敏配置模板到本机 `~/.hermes/config.yaml`（保留本地非占位敏感值）。
- `./scripts/bootstrap.sh all`：新机一次执行 Claude 配置 + Codex 同步。

## 代码风格与命名约定

- Shell 脚本统一使用 Bash，并默认开启 `set -euo pipefail`。
- 退出码语义保持一致：`0` 成功，`1` 失败，`2` 需人工补齐。
- 技能目录名使用小写短横线风格，例如 `openai-docs`、`bird-twitter`。
- 文档优先给出可执行命令、路径与验证步骤，避免空泛描述。

## 输出引用规范

- 默认使用短引用格式：`文件名:行号`。
- 若存在同名文件冲突，再使用最短必要相对路径：`platforms/hermes/README.md:42`。
- 默认不输出长绝对路径和 markdown 可点击绝对路径链接，避免影响可读性。
- 仅当用户明确要求“可点击地址”时，才提供绝对路径链接。
- 同一段落中引用风格保持一致，避免同时混用多种链接样式。

## 输出版式规范

- 终端回答以“先扫到重点”为第一目标；结论、风险、下一步必须尽量前置。
- 一句话能说清的内容不拆列表；并列项达到 3 个再用 bullet。
- 层次最多两级；禁止嵌套 bullet；目录和分层结构改用 ASCII tree 或代码块。
- 目录结构、架构映射、包含关系优先用 fenced code block，不要用 bullet 模拟层级。
- 命令序列、配置片段、对齐清单一律放代码块，不限于“代码”场景。
- 表格只用于列数和行数都足够的多维对比；短清单和两列键值优先用 bullet。
- 强调默认只用加粗；行内代码仅用于路径、命令、变量、函数等代码元素。
- 简单确认类回答不要为了“完整”硬加标题、表格或长列表。

## 测试与验证规范

仓库未统一使用单一测试框架，变更主要通过可执行校验完成：

- 直接运行受影响的 `setup.sh`、`sync_to_codex.sh` 或 `sync_to_hermes.sh`。
- 用 `codex mcp list` 或 `claude mcp list` 验证 MCP 状态。
- 涉及同步逻辑时，默认先做 repo 与本地运行目录 diff；只有在 bootstrap / 灾备场景下，才优先跑脚本。
- 执行同步、提交、推送前，先让读取本仓库的 AI 比较本地 `~/.codex`、`~/.claude` 与仓库受管全局配置的差异；若本次涉及 Hermes，再比较 `~/.hermes/skills` 中 `source=local` 的 skill 与仓库 `platforms/hermes/skills`，并同时比较 `~/.hermes/cron` 与仓库 `platforms/hermes/cron`。
- 忽略 secrets、占位符和运行态噪音；若本地有值得保留的新内容，先回写仓库。

新增技能时，建议提供 `runtime.yaml`；若有 `README.md`，其中至少保留一条验证命令。

## 提交与合并请求规范

提交信息遵循 Conventional Commits，例如：

- `feat(scope): ...`
- `fix(scope): ...`
- `docs: ...`
- `refactor: ...`
- `chore: ...`

每次提交信息必须包含更新摘要标签与中文分点总结：

- 提交信息正文必须包含 `[更新摘要]` 标签。
- `[更新摘要]` 下必须使用中文分点列出本次改动（建议 2-5 条，每条一句）。
- 每次 `git commit` 后必须创建并推送一个 Git annotated tag；tag 注释中也必须包含 `[更新摘要]` 与中文分点总结。
- 推荐 tag 命名：`sync-YYYYMMDD-<short-topic>` 或 `feat-YYYYMMDD-<short-topic>`。

一次提交尽量只覆盖一个平台或一组强相关技能。合并请求需说明改动路径、执行过的验证命令、行为变化与手工步骤。

## 提交前隐私与一致性门禁（必做）

- 隐私扫描：
  - `git grep -nEI "AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|PLAYWRIGHT_MCP_EXTENSION_TOKEN\\s*=\\s*\"[^<\\\"]+\"|x-api-key\\s*[:=]\\s*\"[^<\\\"]+\""`
- diff 完整性检查：
  - `git diff --check && git diff --cached --check`
- 删除后残留引用检查：
  - `git grep -nE "playwright/scripts/playwright_cli\\.sh|playwright/references/cli\\.md|playwright/references/workflows\\.md|\\$PWCLI\\b|@playwright/cli\\b" || true`
- 平台一致性检查（同名 skill 多端存在时）：
  - 同名 skill 允许分叉，但必须确认差异是否属于平台约束，而不是误改。

若发现隐私数据已进入提交历史：

- 立即轮换相关密钥；
- 使用 `git filter-repo` 或 BFG 清理历史并强推；
- 通知协作者重新同步，避免旧提交继续传播。

## 同步一致性与发布门禁

- 以下几处必须保持一致：
  - GitHub 仓库状态
  - 本地项目目录（仓库工作区）
  - 本地 CLI 根目录（`~/.claude`、`~/.codex`；若本次涉及 Hermes，再比较 `~/.hermes` 的 local/DIY subset）
- Claude 平台 skill 日常同步链路：`platforms/claude/skills/<skill>` -> AI 手工 diff -> `~/.claude/skills/<skill>`（最小文件集）。
- Claude 平台 skill 脚本链路：通过 `./setup.sh` 将 `platforms/claude/skills` 应用到本地 Claude 根目录。
- Codex 平台 skill 日常同步链路：`platforms/codex/skills/<skill>` -> AI 手工 diff -> `~/.codex/skills/<skill>`（最小文件集）。
- Codex 平台 skill 脚本链路：`platforms/codex/skills` -> `~/.codex/skills`（`./scripts/sync_to_codex.sh`，主要用于 bootstrap / 灾备）。
- Codex root 受管配置同步链路：`platforms/codex/{AGENTS.md,agents,bin,hooks,scripts,rules}` -> `~/.codex/...`。
- Hermes local-only 链路：`platforms/hermes/skills/<category>/<skill>` <-> `~/.hermes/skills` 中 `source=local` 的同名路径；cron 链路：`platforms/hermes/cron/*` <-> `~/.hermes/cron/*`，仅允许用户手动触发 + 人工审批，不走自动脚本；配置模板链路：`platforms/hermes/config.template.yaml` -> `./scripts/sync_to_hermes.sh` -> `~/.hermes/config.yaml`（仅受管片段合并，保留本地非占位敏感值）。
- 推送 GitHub 前必须获得用户明确确认，不允许自动推送。
- 当用户要求“同步仓库内容”“提交”或“推送”时：先比较相关平台的本地目录与仓库差异；若本地有值得保留的新内容，先提示同步回仓库，再继续后续动作。
- 当处理 `all-my-ai-needs` 的同步任务时，无论方向是“本地运行目录 -> 仓库”还是“仓库 -> 本地运行目录”，任务结束时都必须向用户明确列出同步内容清单；至少包含：新增、更新、删除、跳过/未同步项。
- 当本次改动触发 README 维护条件时：先检查根 `README.md` 与受影响平台 README 是否需要同步更新；若无需更新，需明确说明原因后再继续提交或推送。

## 安全与配置建议

- 禁止提交密钥、令牌和机器私有配置。
- 凭据统一使用环境变量注入。
- 访问 GitHub 相关资源时默认使用本地代理：
  - `HTTP_PROXY=http://127.0.0.1:7897`
  - `HTTPS_PROXY=http://127.0.0.1:7897`
