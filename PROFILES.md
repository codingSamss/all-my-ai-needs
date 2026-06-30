# Skill 同步分层（scope / profile）

本文件定义"哪些 skill 该下发到本地运行目录"的策略，供 **agent 解析后驱动同步**、供 **人审校决策**。

机读真源是各平台的 `platforms/<platform>/skills.meta.yaml`；本文件是它的人读视图与操作剧本。两者冲突时，**以 manifest 为准**，由 agent 核对 manifest 与目录一致。

## 安全铁律

1. **只做正向选择（additive）。** scope / profile 只回答"这次带哪些下发"，绝不用于"不在清单里就删本地 skill"。
2. **保护本地私有 skill。** 本地可能存在 repo 之外的私有 skill（带私有前缀，不公开），它们**永不删除、永不回流仓库**。
3. **治理元数据不下发。** `skills.meta.yaml`、`PROFILES.md`、`runtime.yaml` 只留在仓库，**永不进入** `~/.claude`、`~/.codex`。
4. **分类不含敏感信息。** scope / profile 只用通用分类名，不含任何内网地址、端点、token、集群 / 索引信息。

## scope：是否默认下发

```text
core         始终下发，跨项目通用(git / 交接 / 教学这类基础设施)。
project      仅当对应 profile 激活时下发，绑定特定项目类型。
manual-only  仓库留存，默认不下发，只能由 agent 按名点取。
```

`core` 从严：只有真正每个项目都用得上、触发噪音低的才进。借此把无关 skill 挡在运行目录之外，减少 `description` 触发词互相干扰。

## profile：按项目类型成组拉取

仅 `project` 档的 skill 携带 profile，可多值。当前 5 个：

```text
obsidian-kb       Obsidian 知识库写作与收录
frontend-design   前端设计、动效与出图
social-reading    社交平台只读采集
web-automation    浏览器与截图自动化
macos-local       macOS 本地维护
```

## 成员清单

派生自 `skills.meta.yaml`，改动以 manifest 为准。`core` / `manual-only` 是 scope，其余 5 行是 profile。

| 分类 | 类型 | Codex 成员 | Claude 成员 |
| --- | --- | --- | --- |
| `core` | scope·常驻 | git-ops · handoff · teach | cc-codex-review · git-ops · handoff · skill-creator · teach |
| `obsidian-kb` | profile | official-article-ingest · online-doc-html · orbit-os · orbit-session-diary · video-transcribe | official-article-ingest · online-doc-html · orbit-os · orbit-session-diary · video-transcribe |
| `frontend-design` | profile | fireworks-tech-graph · gsap · ian-xiaohei-illustrations · taste-design | fireworks-tech-graph · gsap · ian-xiaohei-illustrations |
| `social-reading` | profile | bilibili · bird-twitter · linuxdo · reddit · xiaohongshu | bilibili · bird-twitter · linuxdo · reddit · xiaohongshu |
| `web-automation` | profile | playwright · screenshot | playwright · screenshot |
| `macos-local` | profile | mole-mac-cleanup · screenshot | mole-mac-cleanup · screenshot |
| `manual-only` | scope·点名 | openai-docs | — |

平台差异是预期的：`taste-design`、`openai-docs` 仅 Codex；`cc-codex-review`、`skill-creator` 仅 Claude。

## Agent 同步剧本

下发（repo → local）：

```text
1. 读目标平台 skills.meta.yaml。
2. 候选集 = 全部 core + 当前项目激活 profile 的成员；manual-only 仅在用户点名时并入。
3. 对候选集逐个 diff 仓库与运行目录，生成最小变更。
4. 绝不删除候选集之外的本地 skill；绝不下发治理元数据(见铁律 1 / 3)。
5. 把"新增 / 更新 / 跳过"清单摆给人，审批后才 apply。
```

回流（local → repo）：

```text
1. 仅在用户明确要求时进行。
2. 本地私有 / 含内网信息的 skill 绝不回流(见铁律 2)。
3. 同样先 diff、列清单、等人审批，默认禁删。
```

## 真源与校验

```text
真源     platforms/<platform>/skills.meta.yaml(机读，唯一权威)
派生      PROFILES.md 成员表(冲突以 manifest 为准)
校验      由 agent 核对：目录<->manifest 一一对应、scope 合法、profile 已定义
边界      上述文件均 repo-only，永不进入 ~/.claude、~/.codex
```

新增 / 删除 / 重命名 skill 时，先改对应平台的 `skills.meta.yaml`，再由 agent 核对无漂移，最后同步本文件成员表。
