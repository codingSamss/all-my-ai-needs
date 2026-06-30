# cc-codex-review

CC×Codex 交叉讨论技能。不确定性强的问题(事实核查、有争议或乐观的结论、重要技术决策)调 codex 做交叉验证——不同模型 + 独立联网,暴露单模型盲点。

## 工作方式

薄技能,无额外脚本。Claude Code 直接通过 `codex` MCP 工具(`mcp__codex__codex`)与 Codex 对话:

1. 调用时写清背景、要核实/反驳的点,要求联网给来源;
2. 记住返回的 `SESSION_ID`;
3. 续接讨论或下一轮,传**同一个 `SESSION_ID`**(不开新会话);
4. 需要多轮就重复,轮流质疑直到共识;
5. Codex 查证给观点,CC 对账落制品并保证格式。

会话状态由长上下文直接持有;跨会话恢复从 Codex 自己的 `~/.codex/sessions/` 取 `SESSION_ID`。不再需要本地话题文件 / 状态管理脚本(那是 200k 上下文时代的设计,已移除)。

完整方法论见 `SKILL.md`。

## 前置依赖

- 已配置 `codex` MCP Server(未配置时需先用 `claude mcp add` / `codex mcp add` 添加)。

## 设计沿革

早期版本用 `topic-manager.py`(文件持久化话题/会话状态)+ `codex-battle-agent`(多轮辩论执行 agent)。长上下文模型普及后,这两层成为冗余,已下线,逻辑收敛为 SKILL.md 里的直接编排。
