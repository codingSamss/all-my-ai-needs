# Antigravity 平台目录（antigravity）

`platforms/antigravity` 是 Antigravity 平台专属真源。这个 README 负责展示当前 Antigravity agent 的完整精选技能集与平铺同步方式。仓库按 `platform-first` 维护：Antigravity 只关心 `platforms/antigravity` 下的内容，与 `platforms/claude`、`platforms/codex` 互不耦合。

## 同步方式

仓库不提供同步脚本；由 AI agent 拉仓库后执行：

- 读 `platforms/antigravity/skills.meta.yaml` 与 `skills/` 真源，与 `~/.gemini/config/skills` 平铺目录做最小差异 diff 后落盘
- 处理同步/提交/推送请求时，若用户只给目标未明确授权写入（例如“看下本地跟仓库有什么需要同步的”），默认先汇总差异，待用户审批后再写入
- 只下发各 skill `runtime.yaml` 中 `sync_paths` 声明的最小文件集，不下发 `runtime.yaml`、`skills.meta.yaml`、`agents/openai.yaml` 等治理与跨平台元数据
- 全局 `AGENTS.md`、`config.json`、`mcp_config.json` 与 `plugins/`（如 `vibe-island`）由各设备本地自管，不入仓也不由仓库回写

## Skill 同步分层

`platforms/antigravity/skills.meta.yaml` 为每个 skill 标注 `scope` 与能力域 `profile`。由于本地采用平铺目录（`~/.gemini/config/skills/`），本平台仅收录高频、不可被内置能力替代的 15 个精选技能，避免低频技能触发词干扰。

- scope / profile 定义、跨平台成员清单与 agent 同步剧本见根目录 [PROFILES.md](../../PROFILES.md)
- 改动 skill（新增 / 删除 / 重命名）后，先更新 `skills.meta.yaml`，再由 agent 核对 manifest 与目录一致

## 当前 Skills

| Skill | 能力 | 运行说明 |
| --- | --- | --- |
| `bilibili` | B站搜索、热门、排行、视频详情、音频入口与字幕读取 | `bilibili-cli` 包提供的 `bili` 命令为主；OpenCLI 用于字幕，2.x JSON 使用 `ok/data`；完整转录交给 `video-transcribe` |
| `bird-bookmark-folders` | 整理 X/Twitter 收藏夹：列目录、读目录内容、增删移书签、建目录 | 依赖 `python3`；必须与 `bird-twitter` 同时下发到 `~/.gemini/config/skills`；走 GraphQL + Keychain/Chrome Cookie，含写操作 |
| `bird-twitter` | 只读访问 X/Twitter 内容；收藏夹整理交给 `bird-bookmark-folders` | 依赖 Bird CLI（仓库内置包优先）与本地 Keychain 凭据 |
| `fireworks-tech-graph` | 生成带几何校验的技术图，覆盖 12 种风格、工程语义合同、SVG/PNG、语义 SVG→GIF 与离线 HTML | 依赖 Python 3.9+；PNG 优先 `cairosvg`；GIF 动效依赖可选的 Node/FFmpeg/Chromium 工具链 |
| `git-ops` | 按 Sam 习惯安全执行 Git 分支、提交、合并、推送与对比 | 依赖 `git` 与 `rg` |
| `handoff` | 为下一位 agent、新线程或跨机器任务生成临时/持久交接文档 | 纯指令型 skill；临时落点兼容 Unix/Windows；长期接力写入 Obsidian `07_交接台` |
| `ian-xiaohei-illustrations` | 为中文内容生成小黑 2.0 实物场景正文图与长卷故事图 | 直接出图调用 Antigravity 内置 `image-generator` 子代理 |
| `mole-mac-cleanup` | 基于 Mole 官方 agent skill 检查状态、分析磁盘、审计历史并预览清理与应用瘦身 | 1.71.0 基线，旧版按 help 降级；保留个人数据与白名单默认项；卸载/瘦身实跑交用户终端 |
| `mono-color` | 从主题、句子、物件或参考照片生成单色/受控双色的编辑印刷图，覆盖海报、zine、社媒封面与包装 | 直接出图调用 Antigravity 内置 `image-generator` 子代理；`SKILL.md` 与 6 个 catalog 保持上游原字节哈希 |
| `official-article-ingest` | 官方文章收录到 Obsidian，区分原文 1:1 与英文中文对照 1:1，并保持源站排版美感 | 依赖目标 Vault、源站页面与本地媒体校验 |
| `online-doc-html` | Markdown 导出为适合在线文档粘贴的 HTML | 依赖 `pandoc` / `rsvg-convert` |
| `orbit-os` | Obsidian Vault 目录、frontmatter 受控词表与排版规范；新建或修改笔记前读取 | 1.7.1；含 folder note、受控字段、`07_交接台` 与禁新增 `See Also` 规则 |
| `teach` | 在当前 workspace 中进行跨会话、可沉淀的概念与技能教学，并复用课程样式、测验与模拟器组件 | 纯指令型 skill；区分 workspace 与格式文件路径，轮换测验答案位置；建议使用独立学习目录 |
| `video-transcribe` | 视频/音频全量转录、图文笔记与关键帧分析 | 依赖 `yt-dlp` / `ffmpeg` / Groq |
| `xiaohongshu` | 只读访问小红书搜索、笔记、评论、feed、用户公开笔记与媒体下载 | OpenCLI 复用 Chrome 登录态；2.0.3 / 扩展 1.0.27 基线；JSON 先检查 `ok` 再读 `data`；遇风控停止批次 |

## 平台能力资产

- 运行件（全局 `AGENTS.md`、`config.json`、`mcp_config.json`、`plugins/vibe-island`）由各设备本地自管，不入仓
- skill 同步由 AI agent 拉仓库后做最小差异 diff 平铺落到 `~/.gemini/config/skills`
- 隔离环境网页交互与本地预览使用内置 `browser` 子代理；需要复用主 Chrome 登录态的站点走本地 OpenCLI / Keychain CLI 链路
- 生图能力统一使用内置 `image-generator` 子代理；自定义规范与插件维护使用内置 `agy-customizations` 与 `plugin` 技能，不再单独收录外部 `skill-creator`
- 平台级 `platforms/antigravity/runtime.yaml` 与 skill 级 `runtime.yaml` 仅保留在 repo，不同步到 `~/.gemini/config`
