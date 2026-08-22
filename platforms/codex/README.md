# Codex 平台目录（codex）

`platforms/codex` 是 Codex 平台专属真源。这个 README 负责展示当前 Codex agent 的完整能力与同步方式。仓库按 `platform-first` 维护：Codex 只关心 `platforms/codex` 下的内容，不再依赖 `shared/skills/`。

## 同步方式

仓库不提供同步脚本；由 AI agent 拉仓库后执行：

- 读 `platforms/codex/skills.meta.yaml` 与 `skills/` 真源，与 `~/.codex/skills` 做最小差异 diff 后落盘
- 处理同步/提交/推送请求时，若用户只给目标未明确授权写入（例如“看下本地跟仓库有什么需要同步的”），默认先汇总差异，待用户审批后再写入
- 只下发 skill 最小文件集，不下发 `runtime.yaml`、`skills.meta.yaml` 等治理元数据
- `config.toml`、`agents`/`hooks`/`scripts`/`bin` 等运行件由各设备本地自管，不入仓也不由仓库回写
- `~/.codex/skills` 保留 `.system` 与本地未托管技能

## Skill 同步分层

`platforms/codex/skills.meta.yaml` 为每个 skill 标注 `scope`（core / project / manual-only）与项目类型 `profile`，供 agent 决定下发范围。该 manifest 是 repo-only 治理元数据，不下发到 `~/.codex`。

- scope / profile 定义、成员清单与 agent 同步剧本见根目录 [PROFILES.md](../../PROFILES.md)
- 改动 skill（新增 / 删除 / 重命名）后，先更新 `skills.meta.yaml`，再由 agent 核对 manifest 与目录一致

## 当前 Skills

| Skill | 能力 | 运行说明 |
| --- | --- | --- |
| `aihot` | 查询中文 AI 资讯、精选、当前热点、事件时间线、日报与完整精选同步 | 匿名只读 `/api/v1/*`；外部商业或公开再分发需书面授权；按点名方式下发 |
| `apifox-cli` | 通过 CLI 管理 Apifox 接口、Schema、环境、Mock 与项目资源 | 依赖 Apifox CLI 2.2.6+；登录凭据仅保存在本机 |
| `apifox-test-case` | 维护单接口测试用例、请求参数、Body、断言、变量提取与测试数据 | 依赖 `apifox-cli`；写入前校验 schema，写入后回读并运行验证 |
| `bilibili` | B站搜索、热门、排行、视频详情、音频入口与字幕读取 | `bili-cli` 为主；OpenCLI 用于字幕；完整转录交给 `video-transcribe` |
| `bird-twitter` | 只读访问 X/Twitter 内容 | 依赖 Bird CLI（仓库内置包优先） |
| `fireworks-tech-graph` | 生成带几何校验的技术图，覆盖 12 种风格、工程语义合同、SVG/PNG、语义 SVG→GIF 与离线 HTML | 依赖 Python 3.9+；PNG 优先 `cairosvg`；GIF 动效依赖可选的 Node/FFmpeg/Chromium 工具链 |
| `git-ops` | 按 Sam 习惯安全执行 Git 分支、提交、合并、推送与对比 | 依赖 `git` 与 `rg` |
| `gsap` | 前端动效实现辅助，覆盖 GSAP core、React、ScrollTrigger、插件与性能约束 | 依赖 `gsap`，React 项目可加 `@gsap/react` |
| `handoff` | 为下一位 agent、新线程或跨机器任务生成临时/持久交接文档 | 纯指令型 skill；长期接力写入 Obsidian `07_交接台`，建议技能明确通过 Skill tool 调用 |
| `ian-xiaohei-illustrations` | 为中文内容生成小黑 2.0 实物场景正文图与长卷故事图 | 依赖 Codex `image_gen` 能力 |
| `linuxdo` | 只读访问 LINUX DO 论坛 | 依赖 Chrome Cookie |
| `mole-mac-cleanup` | 基于 Mole 官方 agent skill 安全检查状态、分析磁盘、审计历史并预览/执行 macOS 清理 | 依赖 Mole CLI；`purge` 候选须区分本地构建产物与需联网恢复的依赖目录 |
| `official-article-ingest` | 官方文章收录到 Obsidian，区分原文 1:1 与英文中文对照 1:1，并保持源站排版美感 | 依赖目标 Vault、源站页面与本地媒体校验 |
| `online-doc-html` | Markdown 导出为适合在线文档粘贴的 HTML | 依赖 `pandoc` / `rsvg-convert` |
| `orbit-os` | OrbitOS Obsidian Vault 共享配置与规范 | 1.7.1；含 folder note、受控字段、`07_交接台` 与禁新增 `See Also` 规则 |
| `orbit-session-diary` | 基于本地会话日志生成 Obsidian 日记 | 依赖本地 jsonl 与目标 Vault |
| `reddit` | 只读访问 Reddit 内容 | OpenCLI 复用 Chrome 登录态；`rdt-cli` 仅作手动备用 |
| `teach` | 在当前 workspace 中进行跨会话、可沉淀的概念与技能教学，并复用课程样式、测验与模拟器组件 | 纯指令型 skill；建议在独立学习目录中使用 |
| `video-transcribe` | 视频/音频全量转录、图文笔记与关键帧分析 | 依赖 yt-dlp / ffmpeg / Groq |
| `xiaohongshu` | 只读访问小红书搜索、笔记、评论、feed 与用户公开笔记 | OpenCLI 复用 Chrome 登录态；不再保留 HTTP/API 直读路线 |

## 平台能力资产

- 运行件（`agents`/`bin`/`hooks`/`scripts`、`AGENTS.md`、`config.toml`）由各设备本地自管，不入仓
- skill 同步由 AI agent 拉仓库后做最小差异 diff 落到 `~/.codex/skills`
- `platforms/codex/config.toml` 仅作去敏参考，由各设备本地自管，仓库不覆盖本机
- `platforms/codex/config.toml` 已启用 Codex Chrome 插件；浏览器自动化统一走 Codex 内置浏览器与官方 Chrome 插件，不再自维护 playwright skill
- skill 若需要依赖、手动步骤、验证命令，统一写入 repo 中对应 skill 目录下的 `runtime.yaml`
- 平台级 `platforms/codex/runtime.yaml` 仅用于仓库内 AI 理解迁移规则，不会同步到 `~/.codex` 根目录
- skill 级 `runtime.yaml` 仅保留在 repo，不同步到 `~/.codex/skills/<skill>/`
