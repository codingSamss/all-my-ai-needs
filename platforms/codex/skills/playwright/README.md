# playwright

## 作用
通过 `playwright-ext` MCP 驱动真实浏览器，完成页面访问、交互、快照、截图与流程调试。该能力默认关闭，仅在用户明确要求 Playwright Extension 或其他浏览器层无法满足时启用。

## 平台支持
- Codex（已支持）

## 工作原理
统一入口策略（仅一套）：
- 使用手动启用后的 `playwright-ext` MCP（`@playwright/mcp --extension`，复用扩展浏览器会话）
- 本 skill 仅使用 MCP 模式；普通页面和登录态 Chrome 优先走 Codex Browser / Codex Chrome 插件

## 验证命令

```bash
codex mcp get playwright-ext
```

## 依赖
- Node.js / npm / npx
- 手动启用的 `playwright-ext` MCP 配置（`npx @playwright/mcp@latest --extension`）
