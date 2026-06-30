---
name: cc-codex-review
description: "CC×Codex 交叉讨论。不确定性强的问题(事实核查 / 有争议或乐观的结论 / 重要技术决策)找 codex 交叉验证,避免单模型片面。关键词: 让codex看看, 跟codex讨论, codex审查, 帮我审查, review, 交叉讨论, battle, 发给codex, 继续讨论, 接着聊"
---

# CC×Codex 交叉讨论

不确定性强的问题用 codex 做交叉验证——不同模型 + 独立联网,能暴露单模型盲点。本会话用 codex 核实 AI 视频营收数据,就纠正了一批从媒体抓来、其实无法复核的"硬数字"。

## 何时用

- Sam 点名:"让 codex 看看 / 跟 codex 讨论 / 交叉讨论一下 / 发给 codex";
- 或我自己判断结论不确定、容易片面时,主动发起,不必等指令。

## 怎么做

1. 调 `mcp__codex__codex` 工具。PROMPT 写清:背景、要它独立核实或反驳的具体点、要求联网给出来源、并明确"只给结论不要改文件"。`cd` 给相关目录;`sandbox` 默认 `read-only`(只有要 codex 改文件时才用 `workspace-write`)。
2. 记住返回的 `SESSION_ID`。
3. 续接讨论 / 下一轮:再次调用,传**同一个 `SESSION_ID`**,不要开新会话——省算力、保连贯。
4. 多轮 battle:重复 2–3 步,轮流质疑对方结论,直到达成共识或聊够(默认 1 轮;复杂问题 3–5 轮)。
5. 对账落地:codex 负责查证和给观点,我负责对账、改文件并保证格式质量(codex 直接改文件往往格式糙)。不确定的结论降级标注、附来源,分歧如实呈现给 Sam。

## 续接很久以前的讨论

codex 自己把会话存在 `~/.codex/sessions/`。要接旧讨论,从那里找 `SESSION_ID`(或让 Sam 给),传进 `mcp__codex__codex` 即可。不需要本地话题文件来管状态。

## 注意

- 中断或拒绝 codex 调用后,先查进程 + `~/.codex/sessions/` 再续,别盲目重提交(会起重复会话烧算力)。
- 长上下文(1M)下,会话状态我直接在工作上下文里持有,无需文件持久化。
- 行为偏好背景见记忆 `cross-discuss-codex-uncertainty`。
