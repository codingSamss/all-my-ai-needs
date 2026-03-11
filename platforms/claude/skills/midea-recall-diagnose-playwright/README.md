# midea-recall-diagnose-playwright

## 作用
基于 trace/ELK/ES 的 keyword 漏召回排障流程（Playwright 优先）。

## 平台支持
- Claude Code
- Codex（同名 skill 语义保持一致）

## 配置命令

```bash
./setup.sh midea-recall-diagnose-playwright
```

## 验证命令

```bash
./setup.sh list
```

## 依赖
- Python 3
- Claude CLI
- `playwright-ext` MCP（用于浏览器登录态与页面操作）
