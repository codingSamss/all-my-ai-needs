# openai-docs

## 作用
通过 OpenAI 官方开发者文档（MCP）提供可引用、可追溯的最新实现指引。

## 平台支持
- Codex（已支持）

## 工作原理
Skill 优先调用 `openaiDeveloperDocs` MCP 工具，不依赖非官方来源。

## 配置命令

```bash
platforms/codex/skills/openai-docs/setup.sh
```

## 配置脚本行为

- 退出码：`0` 自动完成，`2` 需手动补齐，`1` 执行失败
- 自动检查项：
  - `codex` 命令是否可用
  - `openaiDeveloperDocs` MCP 是否已配置（`codex mcp list`）
- 需手动补齐项：
  - 未安装 Codex CLI
  - 未配置 OpenAI 文档 MCP

## 验证命令

```bash
codex mcp list
```

## 依赖
- Codex CLI
- `openaiDeveloperDocs` MCP（`codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp`）
