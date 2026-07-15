# AI HOT — Agent Skill

让支持 Agent Skills（`SKILL.md`）的工具查询 [AI HOT](https://aihot.virxact.com) 当前精选、最近 7 天公开动态、热点和日报。

匿名只读，无需 API Key。不同 Agent 的目录和授权方式不同，因此安装前应先确认当前平台和目标路径。

## 推荐安装：让 Agent 先审阅再写入

把下面这段发给当前 Agent：

```text
请先检查并安装 AI HOT Skill：https://aihot.virxact.com/aihot-skill/

先读取 SKILL.md、README.md，告诉我你准备写入的目录和文件；不要使用 sudo，不要覆盖其它 Skill。安装完成后告诉我是否需要重启或开启新会话，并给出一个验证问题。
```

来源可直接审阅：

- [SKILL.md](https://aihot.virxact.com/aihot-skill/SKILL.md)
- [install.sh](https://aihot.virxact.com/aihot-skill/install.sh)
- [GitHub 镜像](https://github.com/KKKKhazix/khazix-skills/tree/main/aihot)

## 人类手动安装

先查看脚本，再显式指定平台。脚本不使用 sudo，只写 `SKILL.md` 与 `README.md`。

```bash
# Claude Code
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target claude

# Codex
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target codex

# Gemini CLI
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target gemini

# GitHub Copilot
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target copilot

# OpenCode
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target opencode

# 通用 ~/.agents/skills 目录
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) --target agents
```

自定义目录：

```bash
bash <(curl -fsSL https://aihot.virxact.com/aihot-skill/install.sh) \
  --dir "$HOME/path/to/skills/aihot"
```

## 安装后验证

1. 重启 Agent 或开启新会话。
2. 让 Agent 列出它发现的 skills，确认存在 `aihot`。
3. 提问：`过去 24 小时 AI 圈最重要的 5 件事是什么？`

成功的回答会写明时间窗，给出中文摘要，并把标题链接到 AI HOT 站内阅读页。

## 更新

不要运行一个会默认写入其它平台目录的“通用更新命令”。让当前 Agent 找到它正在加载的文件并覆盖同一目录：

```text
请更新当前已安装的 AI HOT Skill：https://aihot.virxact.com/aihot-skill/
先告诉我当前 aihot/SKILL.md 路径，再覆盖同一目录。
更新后用可识别的非浏览器 User-Agent 验证一次；如果此前出现 blocked / 567，不要继续沿用 Mozilla、Chrome 或 HeadlessChrome UA。
```

手动更新时，重新运行上面的对应 `--target` 或 `--dir` 命令。

旧版 Agent 出现 `blocked / 567` 不等于 IP 被封，通常需要更新 Skill 或修正定时任务的 User-Agent。修正后只重试一次；仍失败请在反馈中附上 `requestId`。

## 能查询什么

- 当前精选与最近 7 天公开池
- 现在最热的多源事件
- 最新或指定日期日报、日报归档
- 模型、产品、行业、论文、技巧分类
- 公司、产品和主题关键词

公开池不等于 AI HOT 全库：公众号、未审内容、低相关条目和已合并重复条目不会返回。

## 内容与署名

Skill 代码使用 MIT License；这不改变第三方原文的版权。对外发布 API 结果时请保留 AI HOT 返回的 `attribution/canonical`，重要引用请回第三方原文核对。

详细接入文档：[aihot.virxact.com/agent](https://aihot.virxact.com/agent)

## 反馈

- [AI HOT 反馈页](https://aihot.virxact.com/feedback)
- [GitHub Skills 镜像](https://github.com/KKKKhazix/khazix-skills/tree/main/aihot)

## License

MIT（仅 Skill 代码与说明文件）
