# openai-docs

## 作用
通过 OpenAI 官方开发者文档（MCP）提供可引用、可追溯的最新实现指引。

## 平台支持
- Codex（已支持）

## 工作原理
Skill 优先调用 `openaiDeveloperDocs` MCP 工具，不依赖非官方来源。

## 验证命令

```bash
codex mcp list
```

## 依赖
- Codex CLI
- `openaiDeveloperDocs` MCP（`codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp`）
