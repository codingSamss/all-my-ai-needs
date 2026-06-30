# playwright

## 作用
通过命令行驱动真实浏览器，完成页面访问、交互、快照、截图与流程调试。

## 平台支持
- Claude Code（已支持）
- Codex（已支持）

## 工作原理
统一入口策略（仅一套）：
- 使用 `playwright-ext` MCP（`@playwright/mcp --extension`，复用扩展浏览器会话）
- 本 skill 仅使用 MCP 模式

## 验证命令

```bash
claude mcp list | rg "playwright-ext"
```

## 依赖
- Node.js / npm / npx
- `playwright-ext` MCP 配置（`npx @playwright/mcp@latest --extension`）
