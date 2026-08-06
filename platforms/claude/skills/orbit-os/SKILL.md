---
name: orbit-os
version: "1.6.1"
updated: 2026-08-06
description: "知识库 OrbitOS Obsidian Vault 共享配置。Vault 结构、格式规则、排版规范。被 orbit-* 系列 skill 自动引用；也可在知识库相关操作中直接调用以获取上下文。"
---
OrbitOS 共享配置，供 orbit-* 系列 skill 自动引用；也可在知识库相关操作中直接调用以获取 Vault 上下文。

# Vault 结构

库路径: 由环境变量 `$OBSIDIAN_VAULT_ROOT` 指定（本地配置注入；典型形如 `$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/<你的 Vault 名>`）

| 目录 | 用途 |
|------|------|
| `01_日记` | 每日日志（按月归档：`YYYY-MM/YYYY-MM-DD.md`） |
| `02_项目` | 活跃项目（一项目一文件夹，单文件小项目直接放根下） |
| `03_研究` | 主动推进的研究领域（一领域一文件夹，各自带导航页） |
| `04_知识沉淀` | 外部知识收录与学习笔记（官方文章、推特精选、主题知识体系） |
| `05_计划` | 执行计划与看板（完成后归档） |
| `06_资产` | 工具资产与可复用配置沉淀 |
| `07_交接台` | 多机器、多 agent 的任务 handoff 与接力索引 |

根目录另有全库入口 `00_Home.md`，汇总七个域的导航页与当前在推进的事；新增顶级栏目时同步更新它。

某些领域在自己目录内定义了更细的归位规则（如 `03_研究/AI 视频制作/方法论/方法论.md` 的四层归位、`导演案例拆解/_检索层/00_语料库总说明.md` 的 grep 检索协议与受控标签表）。与本文件冲突时，域内规则优先。

# 受控字段词表

`area` 与 `status` 是跨目录聚合的依据，取值必须从下表选，**不即兴新造**。新增取值先改本表再使用——同义值分裂（`active` 与 `current` 各写各的）会让按字段筛选静默漏掉结果，与语料库标签词表同理。

`area`（领域，回答「这属于哪个主题」）:

| 取值 | 覆盖 |
|------|------|
| `rag-system` | 公司 RAG 体系全部项目与相关研究 |
| `ai-video` | AI 视频制作全域 |
| `ai-engineering` | Agent / Harness / 上下文工程等 AI 工程主题 |
| `investing` | 美股投资研究 |
| `home-media` | 家庭照片等自建服务 |
| `travel` | 出行计划 |
| `vault-ops` | 知识库自身的配置、资产与工具沉淀 |

`status`（生命周期，回答「这篇还算数吗」）:

| 取值 | 含义 |
|------|------|
| `active` | 在维护，内容可信 |
| `draft` | 未完成，结论不可引用 |
| `reference` | 稳定参考资料，不常改但有效 |
| `deprecated` | 对象已弃用，仅存档回溯，**不可作为当前事实引用** |
| `archived` | 已归档，不再维护 |

标记 `deprecated` / `archived` 时，folder note 正文顶部同时加 `> [!warning]` 说明弃用原因与基线日期；frontmatter 与正文口径必须一致。一个目录整体弃用时，目录下所有文件一起改，不留 `active` 或 `reference` 的散篇。

本词表定于 2026-07-27，存量已于同日迁移完毕（`AI 视频制作`→`ai-video`、`knowledge-base`+`assets`→`vault-ops`、`ai-systems`+`ai-agent`→`ai-engineering`、`家庭照片`→`home-media`、`current`→`active`、`evergreen`→`reference`）。全库取值应全部落在表内，**新增表外取值即为破坏**；需要核对时用 `grep -rh "^area:"` / `grep -rh "^status:"` 现场统计，不在本文件写死篇数。

版本号一类的信息不要塞进 `status`（曾出现 `status: v0`），另起 `version` 字段。

`03_研究/美股投资/` 有自己的 frontmatter schema（用 `type:` 区分文档类型，见该目录 `CLAUDE.md`），`area: investing` 与之并存，不冲突；该目录 `90_教练内部/` 下的 agent 侧文件按其规范豁免 frontmatter 要求，不要给它们补字段。

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

生命周期纪律（不走完 = 索引失真）:

- 任务在等人交东西、等外部结论、等另一台机器时，移进 `03_Blocked/<category>/`，别留在 `02_Active`
- `02_Active` 里的任务超过两周无更新，下次触碰交接台时必须判定：继续推进、转 `03_Blocked`、还是归档
- 归档即整个 `<task_id>/` 目录移入 `04_Archive/YYYY-MM/`，`00_Task.md` 末尾补一段结束说明与日期，不删除内容
- 每次增删任务后同步改 `00_Index.md`，并检查 `00_Home.md` 的「当前在推进」是否需要跟着改

# 结构与元数据规范

- Frontmatter 必须在文件第一行，`---` 开头和结尾
- 多值字段用数组: `tags: [tag1, tag2]`
- 不允许重复键
- `---` 结束后不留空行
- 使用 wikilinks `[[NoteName]]` 连接笔记
- 项目通过 frontmatter 的 `area` 字段关联领域，不用文件夹层级；取值见「受控字段词表」
- 相关链接放在正文底部 `## See Also`，不放 frontmatter
- 外部脚本写入 `.md` 后必须执行 `touch "<file>"`（路径必须加引号/转义）以触发 Obsidian 感知
- 禁止未加引号的 `touch <file>`：含空格文件名会被 shell 拆分，产生意外 0 字节文件

# 引用与路径规范

- 默认使用短引用：`文件名:行号`（例如 `TrainRequestBO.java:46`）
- 若存在同名文件冲突，再使用最短必要相对路径 + 行号
- 默认不输出绝对路径和 markdown 可点击绝对路径链接
- 仅当用户明确要求“可点击地址”时，才提供绝对路径链接
- 同一段落中引用风格保持一致，避免混用

# 媒体资产规范（推特文章，简版）

- 推特精选沉淀路径：`04_知识沉淀/推特精选/<主题分类>/文章名.md`
- 主题分类沿用既有编号目录（`01_Agent 与 Harness 工程`、`02_Claude Code 与 Codex 实战`、`03_上下文与缓存工程`、`04_模型训练与评测`、`05_AI 战略与政策`、`06_学习与知识管理`）；不确定归哪类时先问，不即兴新建
- 文件名格式为 `YYYYMMDD 中文短标题.md`，日期同时写入 frontmatter 的 `date` 与 `updated`
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
- 第一个内容块用 `> [!info]` callout 概括核心目标或文档定位

## 标题层级
- H2 带编号: `## 1. 标题名`
- H3 用于子节，不带编号
- 章节之间用 `---` 分隔

## 强调与标记
- 关键术语首次出现时加粗
- 技术名词、代码符号用行内代码包裹
- 代码块必须标注语言

## Callout 使用
- `> [!info]` 用于关键洞察、原理解释
- `> [!warning]` 用于注意事项、风险提示
- 普通引用块 `>` 用于类比、比喻、形象说明

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

当子 skill（如 orbit-diary）定义的规则与本文件冲突时，子 skill 特例优先于 orbit-os 基线。域内归位规则（见「Vault 结构」末段）同样优先于本文件基线。

# 校验清单

写入 Vault 前必检:

- [ ] Frontmatter 在第一行，无重复键
- [ ] `area` / `status` 取值来自「受控字段词表」，未即兴新造
- [ ] 标 `deprecated` / `archived` 时，正文顶部有对应的 warning callout，口径与 frontmatter 一致
- [ ] H2 带编号
- [ ] 代码块标注语言
- [ ] `## See Also` 在正文底部
- [ ] 引用默认使用短格式（`文件名:行号`），避免长绝对路径
- [ ] 推特精选路径为 `04_知识沉淀/推特精选/<主题分类>/YYYYMMDD 中文短标题.md`
- [ ] 有图文内容时，图片已本地化到同级 `assets/<slug>/` 并使用相对路径引用
- [ ] 链接完整保存任务：已生成正文图片清单（仅正文信息图）
- [ ] 链接完整保存任务：已通过三数一致（预期=下载=引用）
- [ ] 链接完整保存任务：若缺图已标记“未完成”并附缺失清单
- [ ] 动了交接台任务：生命周期已更新，`00_Index.md` 与 `00_Home.md` 已同步
- [ ] 外部写入后执行 `touch`（路径带引号）
- [ ] 批量自动化后执行一次 0 字节巡检：`find <vault> -type f -name '*.md' -size 0`（若命中，先定位再清理）
