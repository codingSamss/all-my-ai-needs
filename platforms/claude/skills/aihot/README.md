# AI HOT — Agent Skill

让支持 Agent Skills（`SKILL.md`）的工具查询 [AI HOT](https://aihot.virxact.com) 的当前精选、最近公开动态、热点和日报，也可低流量维护当前全部精选副本。

基础能力长期保持匿名、只读、无需 API Key。Skill 1.x 使用稳定的 `/api/v1/*` 契约；后端抓取、评分、排序、缓存和模型可以继续迭代，用户无需因此更新 Skill。

## 安装前可审阅

- [SKILL.md](https://aihot.virxact.com/aihot-skill/SKILL.md)
- [安装包清单](https://aihot.virxact.com/aihot-skill/manifest.sha256)
- [install.sh](https://aihot.virxact.com/aihot-skill/install.sh)
- [GitHub 镜像](https://github.com/KKKKhazix/khazix-skills/tree/main/aihot)

## 手动安装

以下 Bash 命令适用于 macOS、Linux 与 WSL。Windows 原生环境请让当前 Agent 按本页说明安装，不要把 Bash 命令直接粘贴到 PowerShell。脚本不会猜测平台，必须显式指定 `--target` 或 `--dir`，无参数只显示帮助并退出。

Codex、Gemini CLI、GitHub Copilot 和 OpenCode 共享 Agent Skills 通用目录 `~/.agents/skills/aihot`：

```bash
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target codex
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target gemini
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target copilot
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target opencode
```

Claude Code 使用自己的目录：

```bash
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target claude
```

显式使用通用目录或自定义目录：

```bash
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target agents

bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) \
  --dir "$HOME/path/to/skills/aihot"
```

安装器先把完整包下载到同一磁盘的临时目录，逐文件验证 SHA-256 与 Skill 身份，全部通过后才一次替换目标目录。安装包只包含运行所需的：

```text
SKILL.md
LICENSE
agents/openai.yaml
references/api.md
references/sync.md
references/errors.md
```

人类说明 `README.md` 不会被放进 Agent 的 Skill 安装目录。

## 旧目录迁移

安装器会检查以下旧位置，防止同名 Skill 被一个 Agent 重复发现：

```text
~/.codex/skills/aihot
~/.gemini/skills/aihot
~/.copilot/skills/aihot
~/.config/opencode/skills/aihot
```

发现旧副本时默认停止，不会静默覆盖或再造一份。确认这些目录都是应被新 1.0 包替换的旧 AI HOT Skill 后，显式迁移：

```bash
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) \
  --target agents \
  --migrate-legacy
```

也可以使用 `--dir <旧目录>` 原地更新单一旧副本；这种方式不会处理其它重复副本。

如果同时给 Claude Code 的专用目录和通用 `~/.agents/skills` 目录安装，同一台机器上兼容多目录的 Agent 可能发现两份 `aihot`。请选择当前 Agent 实际使用的一处安装，并在安装后确认只发现一份。

## 安装后验证

1. 重启 Agent 或开启新会话。
2. 让 Agent 列出它发现的 skills，确认只有一份 `aihot`。
3. 提问：`过去 24 小时 AI 圈最重要的 5 件事是什么？`

成功答案会写明时间窗，给出中文摘要，并把标题链接到 AI HOT 站内阅读页。

## 更新

本地 Skill 不会自动从远端更新。重新运行原来的 `--target` 或 `--dir` 命令即可；更新必须落在当前 Agent 实际加载的那一份上，装到别处只会多出一份副本。稳定 v1 内增加可选字段、后端抓取与排序优化，不要求更新 Skill；只有安全边界、触发范围或主工作流发生破坏性变化时才发布新版。

## 能查询什么

- 过去 24 小时或最近 7 天的精选与公开池；其它 7 天以内范围由 Agent 再收窄。
- 现在最热的多源事件。
- 最新或指定日期日报、日报归档。
- 模型、产品、行业、论文、技巧分类。
- 公司、产品和主题关键词。
- 当前全部精选：首次完整快照，之后只接收新增、编辑和撤选。

公开池不等于 AI HOT 全库：原公众号爆文榜来源（`mp_hot`）、未审内容、低相关条目和已合并重复条目不会返回；正常参与精选的官方／媒体公众号来源仍可能出现。

当前边界：

- 超过 7 天的普通历史搜索暂不保证。
- “最近一周精选”不是 AI HOT 编辑成品周报。正式周报和月报目前只有 [周报网页](https://aihot.virxact.com/weekly) 与 [月报网页](https://aihot.virxact.com/monthly)，尚无 Skill／API／RSS 端点。
- v1 items 返回摘要、AI HOT 阅读页和第三方原文链接，不提供按 ID 获取单篇正文的接口。站内阅读页有权利且已抓到时才显示正文；全文 RSS 也只对允许再分发的来源内联正文。

## 内容、许可与署名

- `LICENSE` 中的 MIT License 只覆盖 Skill 指令与随附文件。
- API 数据适用 [AI HOT 公开接入条款](https://aihot.virxact.com/terms)。
- 第三方原文及全文版权仍归原作者，不因经过 AI HOT 而改变。
- 公开产品只需在页面底部、关于页或数据来源页等正常可发现的位置标注一次「数据来源：AI HOT」并链接本站，无需逐条署名；私人自用或仅内部使用无需界面署名。attribution 与 canonical 继续用于机器识别和追溯；重要引用回第三方原文核对。

详细接入文档：[aihot.virxact.com/agent](https://aihot.virxact.com/agent)

反馈：[aihot.virxact.com/feedback](https://aihot.virxact.com/feedback)
