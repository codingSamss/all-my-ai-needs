# Codex 平台目录（codex）

`platforms/codex` 是 Codex 平台专属真源。这个 README 负责展示当前 Codex agent 的完整能力与同步方式。仓库按 `platform-first` 维护：Codex 只关心 `platforms/codex` 下的内容，不再依赖 `shared/skills/`。

## 同步入口

```bash
./scripts/syncctl.sh check --direction repo-to-local --platform codex --scope all
./scripts/syncctl.sh apply --plan-id <plan_id> --approve-token <token>
./scripts/sync_to_codex.sh
./scripts/sync_to_codex.sh --dry-run
./scripts/sync_to_codex.sh --sync-config
```

说明：

- `syncctl` 是日常入口：默认最小同步口径，支持 `check -> apply` 两阶段令牌审批
- 处理同步/提交/推送请求时，若用户只给目标未明确授权写入（例如“看下本地跟仓库有什么内容需要同步的”），默认先执行 `check` 并汇总，待用户审批后再执行 `apply` / `commit` / `push`
- 默认同步 `platforms/codex/skills/` 与受管 root 配置到 `~/.codex`
- `syncctl --scope all` 不包含 `config.toml`；只有显式 `--scope config` 才会检查 config 差异
- `config.toml` 默认不覆盖本机，仅在显式 `--sync-config` 或 `syncctl --scope config` apply 时同步
- `--sync-config` 覆盖 `config.toml` 时会保留本地 MCP 敏感配置
- `~/.codex/skills` 保留 `.system` 与本地未托管技能
- 日常同步优先由 AI 做最小差异落盘，不直接跑脚本镜像

## Skill 同步分层

`platforms/codex/skills.meta.yaml` 为每个 skill 标注 `scope`（core / project / manual-only）与项目类型 `profile`，供 agent 决定下发范围。该 manifest 是 repo-only 治理元数据，不下发到 `~/.codex`。

- scope / profile 定义、成员清单与 agent 同步剧本见根目录 [PROFILES.md](../../PROFILES.md)
- 改动 skill（新增 / 删除 / 重命名）后，先更新 `skills.meta.yaml`，再运行 `bash scripts/skills_meta_audit.sh` 校验 manifest 与目录一致

## 当前 Skills

| Skill | 能力 | 运行说明 |
| --- | --- | --- |
| `bilibili` | B站搜索、热门、排行、视频详情、音频入口与字幕读取 | `bili-cli` 为主；OpenCLI 用于字幕；完整转录交给 `video-transcribe` |
| `bird-twitter` | 只读访问 X/Twitter 内容 | 依赖 Bird CLI（仓库内置包优先） |
| `fireworks-tech-graph` | 结构化技术图与图片生成（架构图/流程图/时序图/泳道图，SVG+PNG） | 依赖 `python3` 与 `rsvg-convert` |
| `git-ops` | 按 Sam 习惯安全执行 Git 分支、提交、合并、推送与对比 | 依赖 `git` 与 `rg` |
| `gsap` | 前端动效实现辅助，覆盖 GSAP core、React、ScrollTrigger、插件与性能约束 | 依赖 `gsap`，React 项目可加 `@gsap/react` |
| `handoff` | 为下一位 agent、新线程或跨机器任务生成临时/持久交接文档 | 纯指令型 skill；临时写入 OS 临时目录，跨机器长期接力写入 Obsidian `08_交接台` |
| `ian-xiaohei-illustrations` | 为中文内容生成小黑 2.0 实物场景正文图与长卷故事图 | 依赖 Codex `image_gen` 能力 |
| `linuxdo` | 只读访问 LINUX DO 论坛 | 依赖 Chrome Cookie |
| `mole-mac-cleanup` | 安全使用 Mole (`mo`) 预览和清理 macOS 磁盘空间 | 依赖 Mole CLI，推荐 Homebrew 安装 |
| `official-article-ingest` | 官方文章收录到 Obsidian，区分原文 1:1 与英文中文对照 1:1，并保持源站排版美感 | 依赖目标 Vault、源站页面与本地媒体校验 |
| `openai-docs` | OpenAI 官方文档与 API 实现指引 | 依赖官方 docs MCP |
| `online-doc-html` | Markdown 导出为适合在线文档粘贴的 HTML | 依赖 `pandoc` / `rsvg-convert` |
| `orbit-os` | OrbitOS Obsidian Vault 共享配置与规范 | 供 orbit-* 系列 skill 引用；含 `08_交接台` 与 iCloud `AgentArtifacts` 规范 |
| `orbit-session-diary` | 基于本地会话日志生成 Obsidian 日记 | 依赖本地 jsonl 与目标 Vault |
| `playwright` | MCP-only 真实浏览器自动化 | 仅在手动启用 `playwright-ext` 后使用 |
| `reddit` | 只读访问 Reddit 内容 | OpenCLI 复用 Chrome 登录态；`rdt-cli` 仅作手动备用 |
| `screenshot` | 系统级截图与区域捕获 | 使用 OS 级截图能力 |
| `taste-design` | Taste 设计统一入口，按任务路由到前端设计、改版、图到代码、品牌视觉、参考图或 Stitch 子模块 | 运行时只暴露单入口；细分模块保留在 `references/skills/` |
| `teach` | 在当前 workspace 中进行跨会话、可沉淀的概念与技能教学 | 纯指令型 skill；建议在独立学习目录中使用 |
| `video-transcribe` | 视频/音频全量转录、图文笔记与关键帧分析 | 依赖 yt-dlp / ffmpeg / Groq |
| `xiaohongshu` | 只读访问小红书搜索、笔记、评论、feed 与用户公开笔记 | OpenCLI 复用 Chrome 登录态；不再保留 HTTP/API 直读路线 |

## 平台能力资产

- 受管 root 配置：`AGENTS.md`、`agents/`、`bin/`、`hooks/`、`scripts/`、`rules/`
- `./scripts/sync_to_codex.sh` 负责在 bootstrap / 灾备场景下把 `platforms/codex` 应用到 `~/.codex`
- `platforms/codex/config.toml` 默认不自动覆盖本机 `~/.codex/config.toml`，日常全量 `syncctl --scope all` 也不会隐式覆盖
- `platforms/codex/config.toml` 已启用 Codex Chrome 插件；`playwright-ext` 保留配置但默认 `enabled = false`
- skill 若需要依赖、手动步骤、验证命令，统一写入 repo 中对应 skill 目录下的 `runtime.yaml`
- 平台级 `platforms/codex/runtime.yaml` 仅用于仓库内 AI 理解迁移规则，不会同步到 `~/.codex` 根目录
- skill 级 `runtime.yaml` 仅保留在 repo，不同步到 `~/.codex/skills/<skill>/`
- Taste 细分模块不再作为平铺 skill 暴露；统一由 `taste-design` 入口按任务读取 `references/skills/` 下的对应模块
