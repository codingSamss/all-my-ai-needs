# Repository Guidelines

## 项目结构与模块组织

本仓库采用 `platform-first` 模型：`platforms/claude/`、`platforms/codex/` 各自维护各自的平台真源；允许同名 skill 在不同平台目录并存，不强行去重。`shared/` 不再作为主要组织方式。

- `platforms/claude/`：Claude 的 `skills/`、`.claude-plugin/`、`.mcp.json` 模板。
- `platforms/codex/`：Codex 的 `skills/`、`config.toml` 参考。
- 治理元数据：`platforms/{claude,codex}/runtime.yaml`、`skills.meta.yaml`、根 `PROFILES.md`。
- `runtime.yaml` 的字段约定以各平台 `skill_runtime_contract` 为准；平台固定为各自目录对应平台，不再使用 `platform: shared`。

每个技能目录建议包含 `SKILL.md`、`runtime.yaml`；如有确定性脚本或检查，再补 `README.md`。其中 Codex 技能必须有 `SKILL.md`。

## 平台同步策略

- 日常同步默认采用“AI 人工同步 + 差异审阅”，不是直接跑脚本做目录镜像。
- 差异核对前必须先明确口径并在输出中标注：默认使用“日常最小同步口径”（按 runtime.yaml / skills.meta.yaml 规则过滤 repo-only 文件）；仅在用户明确要求“严格镜像/包含删除”时才使用镜像口径。
- 同步由 AI agent 执行：拉仓库后读 `runtime.yaml` / `skills.meta.yaml`，将 skill 真源 diff 后落到运行目录；仓库不再提供同步脚本。
- `runtime.yaml` 必须留在 repo，**不得**下发到 `~/.claude/skills`、`~/.codex/skills`。
- `agents/openai.yaml` 仅在 Codex / OpenAI 风格运行目录确有必要时才下发；Claude 默认不带。
- 内部路由与映射数据不得入仓：本地内部配置（`*.local.*`）、内部系统到集群/索引的映射明细、真实服务路由与端点、集群别名、实例 ID、region/zone 组合、容量类内部表都只能留在本地 ignored 文件中；repo 只允许提交占位符模板（如 `env-config.example.yaml`）。
- 当用户要求“同步某个 skill”时，先比较该平台目录与对应本地运行目录的差异，再执行最小同步并回报结果；不要顺手同步无关 skill。
- 跨平台统一审批约束（Claude/Codex）：当用户提出“同步/提交/推送”或类似“看下本地跟仓库有什么内容需要同步的”但未明确授权执行写入动作时，默认只执行 `check` 与差异汇总；必须等待用户明确批准后，才可继续 `apply` / `commit` / `push`。

## README 维护约定

- 根 `README.md` 负责仓库级能力总览：平台模型、技能概览、平台摘要、同步入口。
- `platforms/{claude,codex}/README.md` 负责对应平台的完整 skill 清单、平台能力资产与同步说明。
- skill 简介默认以对应 `SKILL.md` frontmatter 的 `description` 为准；README 只做压缩，不另写脱离源文案。
- 当新增、删除、重命名 skill，修改 `SKILL.md` 的 `description` 或平台归属，调整平台能力资产、同步入口、用户可见行为时，提交或推送前必须检查并同步更新相关 README。

## 同步与验证操作

仓库不提供同步脚本；下列动作由 AI agent 拉仓库后执行：

- 列出可同步技能：读 `platforms/<platform>/skills.meta.yaml` 与 `skills/` 目录。
- 同步指定技能：将 `platforms/<platform>/skills/<skill>` 的最小文件集 diff 后落到 `~/.claude/skills` 或 `~/.codex/skills`，不下发 `runtime.yaml` 等治理元数据。
- 新机初始化 / 灾备：AI 按 `runtime.yaml` 把全部 skill 真源铺到对应运行目录，并按 `.mcp.json` 模板合并 MCP 配置（不覆盖本机鉴权）。
- 日常优先增量 diff，不做整目录镜像；删除类同步必须用户明确确认。

## 代码风格与命名约定

- Shell 脚本统一使用 Bash，并默认开启 `set -euo pipefail`。
- 退出码语义保持一致：`0` 成功，`1` 失败，`2` 需人工补齐。
- 技能目录名使用小写短横线风格，例如 `openai-docs`、`bird-twitter`。
- 文档优先给出可执行命令、路径与验证步骤，避免空泛描述。

## 输出引用规范

- 默认使用短引用格式：`文件名:行号`。
- 若存在同名文件冲突，再使用最短必要相对路径：`platforms/codex/README.md:42`。
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

- 由 AI 比对受影响 skill 的仓库真源与运行目录差异，确认一致。
- 用 `codex mcp list` 或 `claude mcp list` 验证 MCP 状态。
- 涉及同步逻辑时，由 AI 做 repo 与本地运行目录的 diff，确认最小文件集一致。
- 执行同步、提交、推送前，先让读取本仓库的 AI 比较本地 `~/.codex`、`~/.claude` 与仓库受管全局配置的差异。
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
  - `git ls-files | rg "/references/.*\\.local\\.|/references/.*\\.xlsx$" || true`
  - `git ls-files -o --exclude-standard | rg "/references/.*\\.local\\.|/references/.*\\.xlsx$" || true`
  - 私有敏感模式扫描（敏感模式定义在本地私有规则 `.secrets-patterns.local`，不在公开仓库列举；规则文件缺失时必须明确提示，不可静默当通过）：
    `if [ -f .secrets-patterns.local ]; then rg -nf .secrets-patterns.local . --glob '!**/.git/**' || true; else echo "[提示] 未配置 .secrets-patterns.local（各设备自建），私有敏感模式未扫描"; fi`
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
- 若发现内部环境映射、内部系统映射明细或集群路由数据已被跟踪，必须从当前树删除或改为占位符模板，并补 `.gitignore`；若内容已经推送到不可信远端，再按历史清理流程处理。

## 同步一致性与发布门禁

- 以下几处必须保持一致：
  - GitHub 仓库状态
  - 本地项目目录（仓库工作区）
  - 本地 CLI 根目录（`~/.claude`、`~/.codex`）
- Claude 平台 skill 日常同步链路：`platforms/claude/skills/<skill>` -> AI 手工 diff -> `~/.claude/skills/<skill>`（最小文件集）。
- Codex 平台 skill 日常同步链路：`platforms/codex/skills/<skill>` -> AI 手工 diff -> `~/.codex/skills/<skill>`（最小文件集）。
- `agents`/`hooks`/`scripts`/`bin`、`config.toml` 等运行件由各设备本地自管，不入仓也不由仓库回写。
- 推送 GitHub 前必须获得用户明确确认，不允许自动推送。
- 当用户要求“同步仓库内容”“提交”“推送”或说“看下本地跟仓库有什么内容需要同步的”时：默认先由 AI 做差异检查并输出汇总；若本地有值得保留的新内容，先提示同步回仓库，再等待用户审批后继续执行写入动作。
- 未获得用户明确审批前，禁止执行会产生写入副作用的动作（例如：向运行目录写入同步结果、`git add/commit/push`）。
- 当处理 `all-my-ai-needs` 的同步任务时，无论方向是“本地运行目录 -> 仓库”还是“仓库 -> 本地运行目录”，任务结束时都必须向用户明确列出同步内容清单；至少包含：新增、更新、删除、跳过/未同步项。
- 当本次改动触发 README 维护条件时：先检查根 `README.md` 与受影响平台 README 是否需要同步更新；若无需更新，需明确说明原因后再继续提交或推送。

## 公开仓库安全基线

本仓库为公开仓库，任何设备切换到此仓库、用 agent 提交时，提交前必须满足以下基线：

- 提交身份必须用公开 handle 与 GitHub noreply 邮箱；禁止真实姓名、雇主邮箱或个人常用邮箱进入 git author；提交前确认 `git config user.email` 为 noreply 形式。
- 禁止提交真实个人或环境配置：真实 `config.toml` 的 `[projects]`、`.mcp.json` 真实 server 与端点、`*.local.*`、设备 profile、本地绝对路径、内部服务地址、凭据与 token；公开侧只用 `.example`、占位符或虚构样例。
- 占位符统一用抽象命名：`<PRIVATE_CONFIG_ROOT>`、`<DEVICE_PROFILE>`、`<INTERNAL_ENDPOINT>`、`<COMPANY_DOMAIN>`、`<REAL_NAME>`；举例只用保留域名 `example.com`、`example.internal`、`user@example.com`。
- Skill 必须参数化个人差异：不得硬编码用户名、设备名、Vault 路径、公司域名、内部服务地址或真实项目路径，一律用环境变量、占位符或本地配置注入。
- 泄露风险三档：身份信息、凭据、内网域名与 API、真实运行配置一律阻断；能拼出「组织＋人＋业务」画像的名称默认移除；纯通用技术名低风险容忍。
- 本基线与扫描规则本身也不得泄露：用抽象类别词描述，不在公开仓库列举真实公司词、项目词、内部域名或历史事故细节；具体敏感模式定义在本地私有规则文件 `.secrets-patterns.local`（不入仓）。

## 提交前安全自查（agent 每次提交必跑）

1. `git diff` 与 `git diff --cached` 逐项过目，确认无「仅本机才有的东西」：本地路径、个人或公司项目名、已连服务、设备名、内网地址。
2. 跑「提交前隐私与一致性门禁」的扫描命令（含本地私有规则 `.secrets-patterns.local`）。
3. 确认 `git config user.email` 为 noreply。
4. 禁止 `git add .` 盲提交；只 stage 确认可公开的文件。
5. 命中任何敏感项，先改写为占位符或移出仓库再提交。

## 个人配置不入仓

本仓库只管理通用 skill 与同步脚手架。个人全局配置（Codex `config.toml`、全局 `AGENTS.md` 与 `CLAUDE.md`、`.mcp.json` 真实鉴权等）由各设备在本地运行目录（`~/.codex`、`~/.claude`）自行维护，不纳入本仓库，也不由同步脚本回写；公开侧涉及配置只保留占位符 example。

## 配置与代理

- 凭据统一使用环境变量注入。
- 访问 GitHub 相关资源时默认使用本地代理：
  - `HTTP_PROXY=http://127.0.0.1:7897`
  - `HTTPS_PROXY=http://127.0.0.1:7897`
