# playwright

## 作用
通过 `playwright-ext` MCP 驱动真实浏览器，完成页面访问、交互、快照、截图与流程调试。该能力默认关闭，仅在用户明确要求 Playwright Extension 或其他浏览器层无法满足时启用。

## 平台支持
- Codex（已支持）

## 工作原理
统一入口策略（仅一套）：
- 使用手动启用后的 `playwright-ext` MCP（`@playwright/mcp --extension`，复用扩展浏览器会话）
- 本 skill 仅使用 MCP 模式；普通页面和登录态 Chrome 优先走 Codex Browser / Codex Chrome 插件

## 配置命令

```bash
platforms/codex/skills/playwright/setup.sh
```

## 配置脚本行为

- 退出码：`0` 自动完成，`2` 需手动补齐，`1` 执行失败
- 自动检查项：
  - `playwright-ext` MCP 是否已启用（`codex mcp get playwright-ext` 不能显示 disabled）
  - `npx` 是否可用（`@playwright/mcp` 运行时依赖）
- 需手动补齐项：
  - 没有 Homebrew 且缺少 Node.js/npm
  - 未配置/未启用 `playwright-ext` 或 extension token 无效

## 验证命令

```bash
codex mcp get playwright-ext
```

## 依赖
- Node.js / npm / npx
- 手动启用的 `playwright-ext` MCP 配置（`npx @playwright/mcp@latest --extension`）
