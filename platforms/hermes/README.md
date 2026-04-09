# Hermes 平台目录（hermes）

`platforms/hermes` 记录当前本机 Hermes 的使用态与迁移基线。它不是自动同步真源，也不负责把仓库内容直接写入 `~/.hermes`。

## 当前定位

- 官方安装运行根目录：`~/.hermes`
- 官方源码/安装基线：`~/.hermes/hermes-agent`
- active skills 根目录：`~/.hermes/skills`
- active skills 布局：`~/.hermes/skills/<category>/<skill>`
- 当前仓库职责：记录同名 skill 的落点、允许保留的差异，以及新机手动迁移步骤

## 当前目录基线

以下路径属于当前 Hermes 迁移时需要知道的核心目录：

| 路径 | 用途 | 是否入仓 |
| --- | --- | --- |
| `~/.hermes/config.yaml` | Hermes 主配置 | 否 |
| `~/.hermes/.env` | 凭据与密钥 | 否 |
| `~/.hermes/hermes-agent/` | 官方安装源码与 bundled/optional skills 基线 | 否 |
| `~/.hermes/skills/` | 当前激活 skills | 仅同名 skill 的基线信息入仓 |
| `~/.hermes/skills/.hub/` | Skills Hub 运行态（如 `index-cache`、`quarantine`） | 否 |
| `~/.hermes/skill-promotions/` | skill 提升/重分类过程记录 | 否 |
| `~/.hermes/sessions/`、`~/.hermes/logs/`、`~/.hermes/memories/` | 会话/日志/记忆运行态 | 否 |

## 官方安装 vs 当前本机

基于本机 `~/.hermes/hermes-agent` 与 `~/.hermes/skills` 的比对，当前 Hermes 不是“纯官方安装态”，主要多了以下几类内容：

- 从本仓库/Codex 侧迁入并按类别放置的同名 skills
- Hermes 运行态目录：`.hub/index-cache`、`.hub/quarantine`
- promotion 过程中产生的辅助记录：`~/.hermes/skill-promotions/`
- 本机额外保留但暂未纳入本仓库的平台 skill，例如 `opencode-copilot-opus`

当前 repo 同名 skill 的 Hermes 分类落点，和 `~/.hermes/skill-promotions/20260408-145139/promotion-manifest.json` 一致：

| Skill | Hermes 落点 |
| --- | --- |
| `bird-twitter` | `~/.hermes/skills/social-media/bird-twitter` |
| `context-hub` | `~/.hermes/skills/mcp/context-hub` |
| `google-workspace` | `~/.hermes/skills/productivity/google-workspace` |
| `image-gen` | `~/.hermes/skills/creative/image-gen` |
| `linuxdo` | `~/.hermes/skills/social-media/linuxdo` |
| `llm-wiki` | `~/.hermes/skills/research/llm-wiki` |
| `midea-recall-diagnose-playwright` | `~/.hermes/skills/software-development/midea-recall-diagnose-playwright` |
| `openai-docs` | `~/.hermes/skills/research/openai-docs` |
| `orbit-os` | `~/.hermes/skills/note-taking/orbit-os` |
| `orbit-session-diary` | `~/.hermes/skills/note-taking/orbit-session-diary` |
| `peekaboo` | `~/.hermes/skills/software-development/peekaboo` |
| `pinchtab` | `~/.hermes/skills/software-development/pinchtab` |
| `playwright` | `~/.hermes/skills/software-development/playwright` |
| `reddit` | `~/.hermes/skills/social-media/reddit` |
| `scrapling` | `~/.hermes/skills/research/scrapling` |
| `screenshot` | `~/.hermes/skills/software-development/screenshot` |
| `ui-ux-pro-max` | `~/.hermes/skills/creative/ui-ux-pro-max` |
| `video-transcribe` | `~/.hermes/skills/media/video-transcribe` |
| `xiaohongshu-session-reader` | `~/.hermes/skills/social-media/xiaohongshu-session-reader` |

说明：

- `bird-twitter-bookmarks` 当前仓库有，但 Hermes 本机尚未放置同名 skill。
- `llm-wiki` 现已由仓库 `shared/skills/llm-wiki` 作为共享真源；Hermes 本机副本仅是下游运行态与最小 patch 容器。
- `xitter` 是 Hermes 官方 bundled skill，本机保留在 `~/.hermes/skills/social-media/xitter`。

## 当前差异基线

结论先说：仓库里的共享 skill 以回流后的版本为主，但不是当前 Hermes 的逐字镜像。Hermes 仍会因为官方 bundled skill 演进、手工调整或自优化再次漂移。

当前与仓库同名的 Hermes skills 中，大多数 `SKILL.md` 已与仓库对应版本对齐；仍需持续关注的差异主要集中在 `bird-twitter`、`google-workspace`、`orbit-os`、`midea-recall-diagnose-playwright`，以及新纳入仓库真源管理但仍保留本机 patch 的 `llm-wiki`。

### 已对齐的同名 skills

`context-hub`、`image-gen`、`linuxdo`、`openai-docs`、`orbit-session-diary`、`peekaboo`、`pinchtab`、`playwright`、`reddit`、`scrapling`、`screenshot`、`ui-ux-pro-max`、`video-transcribe`、`xiaohongshu-session-reader`

### 需记录的差异

| Skill | 当前状态 | 处理原则 |
| --- | --- | --- |
| `bird-twitter` | Hermes 版比仓库多一层“本机默认路由 + 代理默认开启 + 归档必须走 `--json-full`”约束 | 下次回流时继续人工审核；暂不自动覆盖 |
| `google-workspace` | Hermes 仍是官方 Python/OAuth 可写版；仓库是 `gogcli` 只读版 | 视为刻意保留的语义分叉，不自动回流到仓库 |
| `llm-wiki` | Hermes 仅保留 `SKILL.md` 与 frontmatter 中的 `metadata.hermes.config`；不保留 `runtime.yaml`、`agents/openai.yaml` 等治理文件 | 作为下游副本处理；只允许人工 diff 后择优回流 |
| `orbit-os` | Hermes 比仓库多一个版本号增量和一条 `08_llm-wiki` 旧目录名说明 | 可在下一次 Orbit 相关回流时一并审核 |
| `midea-recall-diagnose-playwright` | 当前只看到空格/换行风格差异 | 视为非语义差异，可忽略 |

### 重叠/重复能力

`xitter` 与 `bird-twitter` 在 Hermes 中并存：

- `bird-twitter`：当前机器默认用于 X/Twitter 的读流程、时间线、搜索、书签与归档
- `xitter`：保留为官方 API / 写操作能力

如果未来想进一步收敛，可在 Hermes 中用 `hermes skills config` 禁用 `xitter`；当前仓库只记录这个重叠事实，不强制改动本机。

## 新机迁移

建议按下面顺序恢复，不走仓库脚本：

1. 先按 Hermes 官方方式安装，确认 `~/.hermes/hermes-agent`、`~/.hermes/config.yaml`、`hermes` 命令可用。
2. 恢复个人私有配置：`~/.hermes/config.yaml`、`~/.hermes/.env`、必要登录态与 OAuth 文件；这些都不入仓。
3. 按本文件里的“repo 同名 skill 落点表”，把需要保留的同名 skills 放到对应分类目录。
4. 保留 `xitter`、`google-workspace` 这类 Hermes 官方 skill 时，不要假设它们和仓库语义一致；先看本文件“当前差异基线”。
5. 不要把 `.hub/`、`skill-promotions/`、`sessions/`、`logs/`、`memories/` 当作仓库内容迁移。
6. 若之后需要把 Hermes 新变化回写仓库，只比较与仓库同名的 skill，并先输出差异总结给用户审核。

## 校验命令

```bash
hermes skills list
find ~/.hermes/skills -mindepth 2 -maxdepth 2 -type d | sort
find ~/.hermes/skills -mindepth 2 -maxdepth 2 -type d -name 'orbit-*' -o -name 'bird-twitter' -o -name 'google-workspace'
```
