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

## 配置命令

```bash
./setup.sh playwright
# 或直接执行
platforms/claude/skills/playwright/setup.sh
```

## 配置脚本行为

- 退出码：`0` 自动完成，`2` 需手动补齐，`1` 执行失败
- 自动检查项：
  - `playwright-ext` MCP 是否可用（`claude mcp list | rg "playwright-ext"`）
  - `npx` 是否可用（`@playwright/mcp` 运行时依赖）
- 需手动补齐项：
  - 没有 Homebrew 且缺少 Node.js/npm
  - 未配置 `playwright-ext` 或 extension token 无效

## 验证命令

```bash
claude mcp list | rg "playwright-ext"
```

## 依赖
- Node.js / npm / npx
- `playwright-ext` MCP 配置（`npx @playwright/mcp@latest --extension`）
