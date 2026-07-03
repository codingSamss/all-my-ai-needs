# cc-codex-review

CC×Codex 交叉讨论技能。不确定性强的问题(事实核查、有争议或乐观的结论、重要技术决策)调 codex 做交叉验证——不同模型 + 独立联网,暴露单模型盲点。

## 工作方式

薄技能,无额外脚本。Claude Code 通过本机 `codex` CLI 的 `codex exec` 直接调用(不走 MCP):

1. 起会话:`codex exec -s read-only -C <目录> "PROMPT"`,记下头部打印的 `session id`;
2. 续接:`codex exec -s read-only resume <SESSION_ID> "PROMPT"`(同一会话续跑,省算力保连贯;`-s` 必须写在 `resume` 前);
3. 多轮 battle 至共识;Codex 查证给观点,CC 对账落制品并保证格式质量;
4. 长批次委托(批量生图等几十分钟级任务)走 SKILL.md 的「长批次委托」模式:幂等清单指令 + nohup 监工循环自动 resume + 文件监视器。

推理档一律用默认 `xhigh`,不降档。会话存于 `~/.codex/sessions/`,跨会话恢复用 `resume <UUID>` 或 `resume --last`。

完整方法论与实战坑(会话膨胀、残留孤儿、谎报落盘、`-i` 吞 prompt 等)见 `SKILL.md`。

## 前置依赖

- 本机已安装并登录 `codex` CLI。

## 设计沿革

早期版本用 `topic-manager.py`(文件持久化话题/会话状态)+ `codex-battle-agent`(多轮辩论执行 agent),长上下文模型普及后成为冗余,已下线。中期走 `codex` MCP 工具(`mcp__codex__codex`),后因 MCP 长任务易掉线(error -32000)、且受调用方超时钳制,改为 `codex exec` CLI 直调:每轮独立进程、跑完即退,配合 nohup 监工循环可扛几十分钟级批量任务(2026-07 在 OpenMontage 分镜板批量生成中实战验证)。
