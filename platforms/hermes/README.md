# Hermes 平台目录（hermes）

`platforms/hermes` 是当前 Hermes 平台的仓库真源，但只受管一个白名单 subset，不尝试镜像整份 `~/.hermes`。仓库采用 `platform-first`：Hermes 的 skill、cron 与迁移规则都留在 `platforms/hermes/` 下，和 Claude / Codex 分开维护。

## 当前定位

- 官方安装运行根目录：`~/.hermes`
- 官方源码/安装基线：`~/.hermes/hermes-agent`
- active skills 根目录：`~/.hermes/skills`
- active skills 原生布局：`~/.hermes/skills/<category>/<skill>`
- 仓库内 Hermes 真源：`platforms/hermes/skills/<category>/<skill>` 与 `platforms/hermes/cron/`

## 当前受管范围

当前仓库只维护以下 Hermes 内容：

1. 默认按 Codex 同名 skill 对照得到的 Hermes skill
2. `platforms/hermes/managed-extra-skills.txt` 中显式声明的 Hermes-only 例外 skill
3. Hermes cron 相关内容

不纳入仓库的运行态内容：

- `~/.hermes/config.yaml`
- `~/.hermes/.env`
- `~/.hermes/.hub/`
- `~/.hermes/skill-promotions/`
- `~/.hermes/sessions/`、`~/.hermes/logs/`、`~/.hermes/memories/`
- `~/.hermes/cron/output/`

## 仓库目录布局

```text
platforms/hermes/
├── README.md
├── managed-extra-skills.txt
├── runtime.yaml
├── scripts/
│   └── managed_skills.sh
├── skills/
│   ├── autonomous-ai-agents/
│   │   ├── hermes-cron-local-script-notify/
│   │   └── opencode-copilot-opus/
│   ├── creative/
│   │   ├── image-gen/
│   │   └── ui-ux-pro-max/
│   ├── mcp/context-hub/
│   ├── media/video-transcribe/
│   ├── note-taking/
│   │   ├── orbit-os/
│   │   └── orbit-session-diary/
│   ├── productivity/google-workspace/
│   ├── research/
│   │   ├── llm-wiki/
│   │   ├── openai-docs/
│   │   └── scrapling/
│   ├── social-media/
│   │   ├── bird-twitter/
│   │   ├── linuxdo/
│   │   ├── reddit/
│   │   └── xiaohongshu-session-reader/
│   └── software-development/
│       ├── midea-recall-diagnose-playwright/
│       ├── peekaboo/
│       ├── pinchtab/
│       ├── playwright/
│       └── screenshot/
└── cron/
    ├── jobs.json
    └── scripts/
        └── codex_keepalive_notify.py
```

## 受管 skill 判定规则

- 不再手工维护逐项映射表。
- 默认规则：`platforms/codex/skills/<skill>` 与 `platforms/hermes/skills/<category>/<skill>` 同名时，视为 Hermes 受管 skill。
- Hermes-only 例外：写在 `platforms/hermes/managed-extra-skills.txt`，当前用于保留 `hermes-cron-local-script-notify` 这类不在 Codex 中但需要受管的 Hermes skill。
- 本机比对仍然是 repo 路径对同名运行路径：`platforms/hermes/skills/<category>/<skill>` <-> `~/.hermes/skills/<category>/<skill>`。

推荐直接用检查脚本，不再手工数名单：

```bash
bash platforms/hermes/scripts/managed_skills.sh list
bash platforms/hermes/scripts/managed_skills.sh status
bash platforms/hermes/scripts/managed_skills.sh candidates
```

输出含义：

- `list`：列出当前受管的 repo skill，以及来源是 `codex-same-name` 还是 `hermes-extra`
- `status`：列出受管 skill、repo 与本机运行目录的 diff、以及“本机已有但 repo 还没纳管”的 Codex 同名候选
- `candidates`：只列出待补回仓的 Codex 同名候选 skill

## Cron 受管内容

当前仓库已记录：

- `platforms/hermes/cron/jobs.json`
- `platforms/hermes/cron/scripts/codex_keepalive_notify.py`

说明：

- `jobs.json` 是当前已批准入仓的 cron 配置快照
- `cron/output/`、锁文件与运行日志不入仓
- 若 cron 继续扩展，优先把“配置 + 脚本”纳入仓库，而不是把运行结果目录纳入仓库

## 日常同步规则

- Hermes 不走自动脚本同步
- 仅当用户手动触发时，才比较当前受管集合与 `~/.hermes` 的同名路径
- 同步前必须先给出差异总结
- 同步后必须明确汇报：新增、更新、删除、跳过或未同步项

## 新机迁移

建议按下面顺序恢复：

1. 先按 Hermes 官方方式安装，确认 `~/.hermes/hermes-agent`、`~/.hermes/config.yaml`、`hermes` 命令可用。
2. 恢复个人私有配置：`~/.hermes/config.yaml`、`~/.hermes/.env`、必要登录态与 OAuth 文件；这些都不入仓。
3. 按本目录中的 `skills/` 与 `cron/` 手动恢复白名单 subset。
4. 不要迁移 `.hub/`、`skill-promotions/`、`sessions/`、`logs/`、`memories/`、`cron/output/`。
5. 若之后需要把 Hermes 新变化回写仓库，先运行 `bash platforms/hermes/scripts/managed_skills.sh status`，再只比较当前受管集合与同名本机路径，并先输出差异总结给用户审核。

## 校验命令

```bash
hermes skills list
bash platforms/hermes/scripts/managed_skills.sh status
find ~/.hermes/skills -mindepth 2 -maxdepth 2 -type d | sort
cat ~/.hermes/cron/jobs.json
```
