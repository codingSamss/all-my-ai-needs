# reddit

## 作用

通过 OpenCLI 复用用户 Chrome 登录态，只读访问 Reddit（搜索、帖子、评论、subreddit、hot/popular）。

## 平台支持

- Codex（已支持）

## 工作原理

OpenCLI 通过本地 daemon + Chrome 扩展复用浏览器登录态。Skill 只暴露读取类命令，不再默认依赖 Composio MCP。

## 前置条件

- Node.js / npm
- `@jackwener/opencli`
- Chrome OpenCLI extension
- Chrome 已登录 `reddit.com`

安装依赖需要用户单独确认；本仓库不自动安装 OpenCLI、浏览器扩展或写入 Cookie。

## 验证命令

```bash
command -v opencli || true
opencli daemon status
```

注意：日常检查不要用 `opencli doctor`，它可能启动 daemon。

## 使用方式

```bash
opencli reddit search "local llm" -f yaml
opencli reddit read "https://www.reddit.com/r/LocalLLaMA/comments/..." -f yaml
opencli reddit subreddit LocalLLaMA -f yaml
opencli reddit hot -f yaml
opencli reddit popular -f yaml
```

## 备用路线

服务器或存量环境无法使用 OpenCLI 时，可手动配置 `rdt-cli` 作为备用；它同样需要登录态 Cookie，不支持匿名稳定访问。
