# Repository Guidelines

## 项目结构与模块组织
本仓库采用平台隔离设计，`platforms/claude/` 与 `platforms/codex/` 分别维护，互不混用实现细节。

- `platforms/claude/`：Claude 的 `skills/`、`agents/`、`hooks/`、`.claude-plugin/` 与安装脚本。
- `platforms/codex/`：Codex 的 `skills/`（官方加载源）及扩展资产（`agents/`、`hooks/`、`scripts/`）。
- 根脚本：`setup.sh`、`scripts/bootstrap.sh`、`scripts/sync_to_codex.sh`。
- 平台级迁移说明：`platforms/{claude,codex}/runtime.yaml`。
- `runtime.yaml` 的字段约定以各平台 `skill_runtime_contract` 为准；新增 skill 只补目录内容，不修改通用同步设计。

每个技能目录建议包含 `SKILL.md`、`runtime.yaml`；如有确定性脚本或检查，再补 `README.md`、`setup.sh`。其中 Codex 技能必须有 `SKILL.md`。

## README 维护约定
- 根 `README.md` 负责仓库级能力总览：共用 skills、平台差异 skills、平台能力摘要、同步入口。
- `platforms/{claude,codex}/README.md` 负责对应平台的完整 skill 清单、平台能力资产与同步说明。
- skill 简介默认以对应 `SKILL.md` frontmatter 的 `description` 为准；README 只做压缩，不另写脱离源文案。
- 当新增、删除、重命名 skill，修改 `SKILL.md` 的 `description` 或平台归属，调整平台能力资产、同步入口、用户可见行为时，提交或推送前必须检查并同步更新相关 README。

## 构建、测试与开发命令
- `./setup.sh list`：列出可执行配置的 Claude 技能。
- `./setup.sh all`：执行 Claude 的核心配置与全部技能配置。
- `./setup.sh <skill...>`：仅配置指定技能。
- `./scripts/sync_to_codex.sh --dry-run`：预览 Codex 配置同步结果。
- `./scripts/sync_to_codex.sh`：同步 `platforms/codex/skills` 与受管 root 配置到 `~/.codex`（默认不覆盖本机 `config.toml`）。
- `./scripts/sync_to_codex.sh --sync-config`：显式同步 `platforms/codex/config.toml` 到 `~/.codex/config.toml`。
- `./scripts/bootstrap.sh all`：新机一次执行 Claude 配置 + Codex 同步。

## 代码风格与命名约定
- Shell 脚本统一使用 Bash，并默认开启 `set -euo pipefail`。
- 退出码语义保持一致：`0` 成功，`1` 失败，`2` 需人工补齐。
- 技能目录名使用小写短横线风格，例如 `openai-docs`、`bird-twitter`。
- 文档优先给出可执行命令、路径与验证步骤，避免空泛描述。

## 输出引用规范
- 默认使用短引用格式：`文件名:行号`（例如 `TrainRequestBO.java:46`）。
- 若存在同名文件冲突，再使用最短必要相对路径：`domain/.../TrainRequestBO.java:46`。
- 默认不输出长绝对路径和 markdown 可点击绝对路径链接，避免影响可读性。
- 仅当用户明确要求“可点击地址”时，才提供绝对路径链接。
- 同一段落中引用风格保持一致，避免同时混用多种链接样式。

## 测试与验证规范
仓库未统一使用单一测试框架，变更主要通过可执行校验完成：

- 直接运行受影响的 `setup.sh`。
- 用 `codex mcp list` 或 `claude mcp list` 验证 MCP 状态。
- 涉及同步逻辑时，先跑 `./scripts/sync_to_codex.sh --dry-run` 再正式执行。
- 执行同步、提交、推送前，先让读取本仓库的 AI 比较本地 `~/.codex`、`~/.claude` 与仓库受管全局配置的差异；忽略 secrets、占位符和运行态噪音，若本地有值得保留的新内容，先回写仓库。

新增技能时，必须提供 `runtime.yaml`；若有 `README.md`，其中至少保留一条验证命令。

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
- 推荐 tag 命名：`sync-YYYYMMDD-<short-topic>` 或 `feat-YYYYMMDD-<short-topic>`（短主题使用小写短横线）。
- 示例：
  - `docs(sync): 同步浏览器 MCP 配置`
  - `[更新摘要]`
  - `- 新增 Codex 侧 chrome-devtools MCP 模板配置。`
  - `- 新增 Claude 侧 chrome-devtools MCP 模板配置。`
  - `- 更新 README 的同步说明与注意事项。`
  - `git tag -a sync-20260314-mcp-template -m "[更新摘要]" -m "- 新增 ..." -m "- 调整 ..."`

一次提交尽量只覆盖一个平台或一个技能。合并请求需说明改动路径、执行过的验证命令、行为变化与手工步骤。

### 提交前隐私与一致性门禁（必做）
- 隐私扫描（禁止真实密钥/令牌入库，允许占位符）：
  - `git grep -nEI "AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|PLAYWRIGHT_MCP_EXTENSION_TOKEN\\s*=\\s*\"[^<\\\"]+\"|x-api-key\\s*[:=]\\s*\"[^<\\\"]+\""`
- diff 完整性检查（禁止空白错误/坏补丁）：
  - `git diff --check && git diff --cached --check`
- 删除后残留引用检查（防止文档/脚本断链）：
  - `git grep -nE "playwright/scripts/playwright_cli\\.sh|playwright/references/cli\\.md|playwright/references/workflows\\.md|\\$PWCLI\\b|@playwright/cli\\b" || true`
- 双平台一致性检查（同名 skill 双端存在时）：
  - `platforms/claude/skills/<skill>` 与 `platforms/codex/skills/<skill>` 的命令语义必须一致，仅允许平台路径差异。

若发现隐私数据已进入提交历史：
- 立即轮换相关密钥；
- 使用 `git filter-repo` 或 BFG 清理历史并强推；
- 通知协作者重新同步，避免旧提交继续传播。

## 同步一致性与发布门禁
- 以下三处必须保持一致：
  - GitHub 仓库状态
  - 本地项目目录（仓库工作区）
  - 本地 CLI 根目录（`~/.claude`、`~/.codex`）
- Codex 同步链路：`platforms/codex/skills` -> `~/.codex/skills`（`./scripts/sync_to_codex.sh`）。
- Codex root 受管配置同步链路：`platforms/codex/{AGENTS.md,agents,bin,hooks,scripts,rules}` -> `~/.codex/...`。
- `platforms/codex/config.toml` 默认不自动覆盖 `~/.codex/config.toml`；仅在显式 `--sync-config` 时同步。
- Claude 同步链路：通过 `./setup.sh` 将仓库配置应用到本地 Claude 根目录。
- 推送 GitHub 前必须获得用户明确确认，不允许自动推送。
- 当用户要求“同步仓库内容”“提交”或“推送”时：先比较本地 `~/.codex`、`~/.claude` 与仓库受管全局配置；忽略 secrets、占位符和运行态噪音，若本地有值得保留的新内容，先提示同步回仓库，再继续后续动作。
- 当本次改动触发 README 维护条件时：先检查根 `README.md` 与受影响平台 README 是否需要同步更新；若无需更新，需明确说明原因后再继续提交或推送。

## 安全与配置建议
- 禁止提交密钥、令牌和机器私有配置。
- 凭据统一使用环境变量注入。
- 访问 GitHub 相关资源时默认使用本地代理：
  - `HTTP_PROXY=http://127.0.0.1:7897`
  - `HTTPS_PROXY=http://127.0.0.1:7897`
