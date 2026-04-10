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

1. 当前从 Codex 复制到 Hermes 的同名 skill
2. `llm-wiki`
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
├── runtime.yaml
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

## 白名单技能映射

| Repo 路径 | 本机运行路径 |
| --- | --- |
| `platforms/hermes/skills/social-media/bird-twitter` | `~/.hermes/skills/social-media/bird-twitter` |
| `platforms/hermes/skills/mcp/context-hub` | `~/.hermes/skills/mcp/context-hub` |
| `platforms/hermes/skills/productivity/google-workspace` | `~/.hermes/skills/productivity/google-workspace` |
| `platforms/hermes/skills/creative/image-gen` | `~/.hermes/skills/creative/image-gen` |
| `platforms/hermes/skills/social-media/linuxdo` | `~/.hermes/skills/social-media/linuxdo` |
| `platforms/hermes/skills/research/llm-wiki` | `~/.hermes/skills/research/llm-wiki` |
| `platforms/hermes/skills/software-development/midea-recall-diagnose-playwright` | `~/.hermes/skills/software-development/midea-recall-diagnose-playwright` |
| `platforms/hermes/skills/research/openai-docs` | `~/.hermes/skills/research/openai-docs` |
| `platforms/hermes/skills/note-taking/orbit-os` | `~/.hermes/skills/note-taking/orbit-os` |
| `platforms/hermes/skills/note-taking/orbit-session-diary` | `~/.hermes/skills/note-taking/orbit-session-diary` |
| `platforms/hermes/skills/software-development/peekaboo` | `~/.hermes/skills/software-development/peekaboo` |
| `platforms/hermes/skills/software-development/pinchtab` | `~/.hermes/skills/software-development/pinchtab` |
| `platforms/hermes/skills/software-development/playwright` | `~/.hermes/skills/software-development/playwright` |
| `platforms/hermes/skills/social-media/reddit` | `~/.hermes/skills/social-media/reddit` |
| `platforms/hermes/skills/research/scrapling` | `~/.hermes/skills/research/scrapling` |
| `platforms/hermes/skills/software-development/screenshot` | `~/.hermes/skills/software-development/screenshot` |
| `platforms/hermes/skills/creative/ui-ux-pro-max` | `~/.hermes/skills/creative/ui-ux-pro-max` |
| `platforms/hermes/skills/media/video-transcribe` | `~/.hermes/skills/media/video-transcribe` |
| `platforms/hermes/skills/social-media/xiaohongshu-session-reader` | `~/.hermes/skills/social-media/xiaohongshu-session-reader` |
| `platforms/hermes/skills/autonomous-ai-agents/opencode-copilot-opus` | `~/.hermes/skills/autonomous-ai-agents/opencode-copilot-opus` |
| `platforms/hermes/skills/autonomous-ai-agents/hermes-cron-local-script-notify` | `~/.hermes/skills/autonomous-ai-agents/hermes-cron-local-script-notify` |

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
- 仅当用户手动触发时，才比较仓库白名单目录与 `~/.hermes` 的同名路径
- 同步前必须先给出差异总结
- 同步后必须明确汇报：新增、更新、删除、跳过或未同步项

## 新机迁移

建议按下面顺序恢复：

1. 先按 Hermes 官方方式安装，确认 `~/.hermes/hermes-agent`、`~/.hermes/config.yaml`、`hermes` 命令可用。
2. 恢复个人私有配置：`~/.hermes/config.yaml`、`~/.hermes/.env`、必要登录态与 OAuth 文件；这些都不入仓。
3. 按本目录中的 `skills/` 与 `cron/` 手动恢复白名单 subset。
4. 不要迁移 `.hub/`、`skill-promotions/`、`sessions/`、`logs/`、`memories/`、`cron/output/`。
5. 若之后需要把 Hermes 新变化回写仓库，只比较仓库已受管的同名路径，并先输出差异总结给用户审核。

## 校验命令

```bash
hermes skills list
find ~/.hermes/skills -mindepth 2 -maxdepth 2 -type d | sort
cat ~/.hermes/cron/jobs.json
```
