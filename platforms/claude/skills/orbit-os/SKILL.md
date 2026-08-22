---
name: orbit-os
description: "知识库 OrbitOS Obsidian Vault 共享配置。Vault 结构、格式规则、排版规范。被 orbit-* 系列 skill 自动引用；也可在知识库相关操作中直接调用以获取上下文。"
metadata:
  version: "1.7.1"
  updated: "2026-08-22"
---
OrbitOS 共享配置，供 orbit-* 系列 skill 自动引用；也可在知识库相关操作中直接调用以获取 Vault 上下文。

# Vault 结构

库路径: 由环境变量 `$OBSIDIAN_VAULT_ROOT` 指定（本地配置注入；典型形如 `$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/<你的 Vault 名>`）

| 目录 | 用途 |
|------|------|
| `01_日记` | 每日日志（按月归档：`YYYY-MM/YYYY-MM-DD.md`） |
| `02_项目` | 活跃项目（每个项目一个文件夹，单文件小项目直接放根下） |
| `03_研究` | 主动研究的领域（每个领域一个文件夹） |
| `04_知识沉淀` | 原子概念笔记、官方文章与推特精选 |
| `05_计划` | 执行计划（完成后归档） |
| `06_资产` | 工具资产与可复用配置沉淀 |
| `07_交接台` | 多机器、多 agent 的任务 handoff 与接力索引 |

没有 `05_资讯` 目录；策展内容归入 `04_知识沉淀`。目录编号即为实际结构，不要另建编号。

根目录的 `00_Home.md` 是全库入口，汇总七个域的导航页与当前在推进的事项；新增顶级栏目或调整导航时同步更新它。

每个目录及其子领域用 **folder note**（文件名 = 目录名，如 `03_rag-flow/03_rag-flow.md`）作为入口，`folder-notes` 插件据此让目录可点击。新建子领域目录时一并建 folder note，并加 `folder-note` 标签。例外：目录自带 `AGENTS.md`/`CLAUDE.md` 且声明了唯一入口的（如 `03_研究/美股投资`），遵从该目录的约定，不要新增第二个入口文件。

部分领域在自己的目录内定义更细的归位、检索或元数据规则；与本文件冲突时，域内规则优先。

# Agent 交接台规范

`07_交接台` 只保存可读的 Markdown 交接信息、索引和外部资产链接；大型产物、视频、压缩包、下载物、中间处理文件统一放到 iCloud Drive 顶级目录 `AgentArtifacts/`，不要放进 Obsidian Vault。

推荐结构:

```text
07_交接台/
  00_Index.md
  01_Inbox/
  02_Active/
    project/
    research/
    knowledge/
    ops/
    media/
  03_Blocked/
    project/
    research/
    knowledge/
    ops/
    media/
  04_Archive/
    YYYY-MM/
  90_Templates/
    task.md
    handoff.md
    assets.md
```

外部资产结构与任务 `task_id` 对齐:

```text
iCloud Drive/AgentArtifacts/
  00_Inbox/
  01_Active/
    project/
    research/
    knowledge/
    ops/
    media/
  02_Archive/
```

任务目录规则:

- `task_id` 使用 `<YYYY-MM-DD>-<english-slug>`，例如 `2026-06-29-openmontage-douyin-tutorial`
- 每个正式任务必须有父目录: `07_交接台/<lifecycle>/<category>/<task_id>/`
- 分类固定为 `project`、`research`、`knowledge`、`ops`、`media`
- `00_Task.md` 是当前真相，记录目标、状态、下一步、owner machine、最新 handoff 和外部资产根
- `01_Assets.md` 只记录 `AgentArtifacts/<lifecycle>/<category>/<task_id>/` 下的大文件索引，不内嵌大文件
- 单次交接文件命名为 `<YYYY-MM-DD-HHMM>__<topic-slug>.md`（`topic-slug` 为本次交接重点的英文短 slug），例如 `2026-06-29-1451__douyin-tutorial-research.md`；机器与 agent 写进 frontmatter 的 `machine` / `agent`，不放进文件名
- handoff 文件按 append-only 处理；要更新当前状态时改 `00_Task.md`，不要回写旧 handoff
- 生命周期为 `01_Inbox -> 02_Active -> 03_Blocked -> 04_Archive/YYYY-MM`
- 外部写入 `07_交接台` 内 `.md` 后必须执行 `touch "<file>"`

生命周期纪律：

- 等待用户、外部结论或另一台机器时，把任务移到 `03_Blocked/<category>/`，不要继续留在 `02_Active`
- `02_Active` 中超过两周未更新的任务，下次触碰时必须判断继续推进、转 Blocked 或归档
- 归档时移动整个 `<task_id>/` 到 `04_Archive/YYYY-MM/`，并在 `00_Task.md` 记录结束说明与日期；不要删除历史 handoff
- 每次增删或移动任务后同步维护 `00_Index.md`，并检查根 `00_Home.md` 的“当前在推进”是否需要更新

# 结构与元数据规范

- Frontmatter 必须在文件第一行，`---` 开头和结尾
- 多值字段用数组: `tags: [tag1, tag2]`
- 不允许重复键
- `---` 结束后不留空行
- 使用 wikilinks `[[NoteName]]` 连接笔记
- 项目通过 frontmatter 的 `area` 字段关联领域，不用文件夹层级
- **新文不写 `## See Also` 段**：文末互链与索引、正文或文件树导航重复。存量仍有旧段落，触碰相关文档时逐步迁移到正文行文、索引页或 folder note，不为清理而批量改写无关内容
- 外部脚本写入 `.md` 后必须执行 `touch "<file>"`（路径必须加引号/转义）以触发 Obsidian 感知
- 禁止未加引号的 `touch <file>`：含空格文件名会被 shell 拆分，产生意外 0 字节文件

# 受控字段词表

`area` 与 `status` 用于跨目录聚合，必须从下列取值中选择；需要新值时先更新本表，不能在单篇文档中即兴创建同义值。

`area`：

| 取值 | 覆盖 |
|---|---|
| `rag-system` | RAG 体系项目与研究 |
| `ai-video` | AI 视频制作 |
| `ai-engineering` | Agent、Harness 与上下文工程 |
| `investing` | 投资研究 |
| `home-media` | 家庭媒体与自建服务 |
| `travel` | 出行计划 |
| `vault-ops` | 知识库配置、资产与工具沉淀 |

`status`：

| 取值 | 含义 |
|---|---|
| `active` | 正在维护，内容可信 |
| `draft` | 尚未完成，结论不可直接引用 |
| `reference` | 稳定参考资料 |
| `deprecated` | 对象已弃用，仅供回溯 |
| `archived` | 已归档，不再维护 |

- 存量可能仍有旧值 `archive`；不要新建该值，触碰对应文档且语义确认无误时迁移为 `archived`
- 标记 `deprecated` 或 `archived` 时，在正文顶部增加 `> [!warning]`，说明原因和基线日期，并确保 frontmatter 与正文一致
- 版本信息使用独立 `version` 字段，不要写进 `status`
- 目录自有 frontmatter schema 时遵循域内规则，`area` 可与域内 `type` 等字段并存

# 引用与路径规范

- 默认使用短引用：`文件名:行号`（例如 `TrainRequestBO.java:46`）
- 若存在同名文件冲突，再使用最短必要相对路径 + 行号
- 默认不输出绝对路径和 markdown 可点击绝对路径链接
- 仅当用户明确要求“可点击地址”时，才提供绝对路径链接
- 同一段落中引用风格保持一致，避免混用

# 媒体资产规范（推特文章，简版）

- canonical 原文放 `04_知识沉淀/推特精选/<NN_主题分类>/YYYYMMDD 中文短标题.md`；现有分类：`01_Agent 与 Harness 工程`、`02_Claude Code 与 Codex 实战`、`03_上下文与缓存工程`、`04_模型训练与评测`、`05_AI 战略与政策`、`06_学习与知识管理`。按主题归类，不按作者建目录
- **文件名必须带 `YYYYMMDD ` 日期前缀**（与官方文章一致），同时写入 frontmatter 的 `date` 与 `updated`
- 互链必须连日期前缀一起写：`[[Anthropic 官方文章/Claude Blog/20260123 构建多智能体系统：何时以及如何使用它们]]`，漏掉前缀即断链
- 厂商官方文章走 `04_知识沉淀/<厂商> 官方文章/<栏目>/YYYYMMDD 标题.md`（栏目如 Claude Blog、Engineering、Talks），栏目目录各自带 folder note
- 有图时默认本地化到同级目录：`.../assets/<slug>/`
- 图片文件名使用顺序编号：`img-0.ext`、`img-1.ext`、`img-2.ext`（保留原扩展名）
- 文内图片使用相对路径：`![图 1｜说明](assets/<slug>/img-0.jpg)`，建议补一行图注
- 仅当用户明确要求“只保留外链”时，才允许不落地图片

# 媒体资产规范（链接完整保存，通用）

- 触发：用户提供链接并要求“完整保存/完整还原/原文转录/含图保存/1:1 保留”
- 范围：`03_研究/`、`04_知识沉淀/`
- 落地：文档写入目标栏目；图片保存到同级 `assets/<slug>/`，命名 `img-0.ext`、`img-1.ext`（保留扩展名）
- 引用：正文只用相对路径；仅在用户明确要求时保留外链
- 统计口径：只算正文信息图，忽略 logo/头像/分享按钮等装饰图
- 优先级：推特文章仍优先使用“推特文章规范”

## 完成条件（DoD）

- 若源文正文有图，必须满足：`预期图片数 = 下载成功数 = 文内引用数`
- 任一不相等即未完成；缺图必须阻塞交付并附缺失清单

## 最小流程

1. 识别正文图片并记录预期数量
2. 下载到 `assets/<slug>/`，正文按原位插图（相对路径）
3. 做三数一致校验（预期=下载=引用）
4. 外部写入 `.md` 后执行 `touch "<file>"`（必须加引号）

## 缺图模板

```text
状态：未完成（缺图）
- img-<n> | <url> | <reason> | <attempts>
处理：阻塞交付，待补齐后再完成。
```

# 内容呈现规范

输出到 Obsidian 的文档必须遵循以下排版风格:

## 文档开头
- 第一个内容块用 `> [!info]` callout 概括文档定位与读法
- 措辞要直接，不套模板句式（避免千篇一律的「这是 X 的入口。它不替代 Y，而是 Z」）；一两句话说清这篇文章回答什么问题、怎么读

## 标题层级
- 不写 `# H1`（标题由 frontmatter `title` 或文件名承载）；正文从 `## ` 开始
- H2 带编号: `## 1. 标题名`
- H3 带父级编号: `### 1.1 子节名`（同一 H2 下有多个 H3 时使用；仅一个 H3 可省略编号）
- 最深不超过 H3，不使用 H4 及以下
- 章节之间用 `---` 分隔

## 强调与标记
- 关键术语首次出现时加粗
- 技术名词、代码符号用行内代码包裹
- 代码块必须标注语言（纯文本用 `text`，不留空）

## Callout 使用（仅三种）
- `> [!info]` — 文档定位、读法指引、设计说明、关键洞察
- `> [!warning]` — 有时效性、有风险、容易踩坑的信息
- `> [!example]` — 路线卡、决策条目、结构化示例
- **不使用** `tip`、`summary`、`abstract`、`note`（存量逐步清理）
- 普通引用块 `>` 用于类比、比喻等非结构化引述
- 单篇 callout 总数控制在 5 个以内（语料库等特殊格式除外）

## 图片规范
- alt-text 写一句话描述图片是什么（不超过 30 字），不留空，不塞长段落
- 图注统一为图下一行斜体: `*图 N｜一句话说明*`
- 尺寸控制: 信息图/架构图建议 `![[path|720]]`；截图/示意图按需缩放
- 标准 Markdown `![alt](path)` 和 Obsidian `![[path]]` 均可，同篇内保持一致

## 内容组织
- 复杂概念先给出简短直觉解释，再展开细节
- 对比说明用并列代码块或表格
- 每个主要章节结尾可加引导思考或小结

# 日记填充规则

写日记（`01_日记/YYYY-MM/YYYY-MM-DD.md`）时，`## 日志` 部分应自动从 GitHub 拉取当天跨仓库的 commit 记录。

- GitHub 用户名: `codingSamss`
- 数据源: `gh api` Events API + Commits API
- 不加 `author` 参数，避免邮箱不匹配

## 写入格式

按仓库分组，每个仓库一个 H3，附 commit 数量。每条 commit 用列表项，末尾括号标 short sha。同仓库多条 commit 归纳出一句主线描述。

```markdown
### {repo}（N commits）

主线：一句话概括本仓库今天的改动方向

- commit 描述（`sha`）
- commit 描述（`sha`）
```

# 项目笔记结构 (C.A.P.)

- **背景 (Context)**: 目标、背景、为什么重要
- **行动 (Actions)**: 阶段/里程碑与任务
- **进展 (Progress)**: 更新记录

最小模板:

```markdown
---
area:
tags: [project]
status: active
---
## Context
## Actions
## Progress
```

# 规范优先级

当子 skill（如 orbit-diary）定义的规则与本文件冲突时，子 skill 特例优先于 orbit-os 基线。

# 校验清单

写入 Vault 前必检:

- [ ] Frontmatter 在第一行，无重复键
- [ ] `area` / `status` 使用受控词表；旧 `status: archive` 在确认语义后迁移为 `archived`
- [ ] 不写 H1；正文从 `## 1.` 开始，H3 用 `### 1.1` 子编号
- [ ] 代码块标注语言（纯文本用 `text`）
- [ ] Callout 只用 `info`/`warning`/`example` 三种，总数 ≤5
- [ ] 图片 alt-text 非空且不超 30 字；图下一行有斜体图注
- [ ] 没有新增 `## See Also` 段；存量仅在触碰对应文档时迁移
- [ ] 引用默认使用短格式（`文件名:行号`），避免长绝对路径
- [ ] 推特/官方文章路径与文件名带 `YYYYMMDD ` 日期前缀，互链也带前缀
- [ ] 有图文内容时，图片已本地化到同级 `assets/<slug>/` 并使用相对路径引用
- [ ] 链接完整保存任务：已生成正文图片清单（仅正文信息图）
- [ ] 链接完整保存任务：已通过三数一致（预期=下载=引用）
- [ ] 链接完整保存任务：若缺图已标记“未完成”并附缺失清单
- [ ] 动了交接台任务：生命周期、`00_Index.md` 与根 `00_Home.md` 已同步
- [ ] 外部写入后执行 `touch`（路径带引号）
- [ ] 批量自动化后执行一次 0 字节巡检：`find <vault> -type f -name '*.md' -size 0`（若命中，先定位再清理）
