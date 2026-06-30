# reddit

## 作用

通过 OpenCLI 复用用户 Chrome 登录态，只读访问 Reddit：搜索帖子、读取帖子与评论、浏览 subreddit 与 hot/popular feed。

## 平台支持

- Claude（已支持）

## 工作原理

OpenCLI 使用本地 daemon + Chrome 扩展复用真实浏览器登录态。这个 skill 只暴露读取类命令，不再依赖 Composio MCP / 远程 OAuth。

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

服务器或存量非桌面环境无法使用 OpenCLI 时，可手动配置 `rdt-cli` 作为备用；它同样需要登录态 Cookie，不支持匿名稳定访问。

## 边界

- 只读，不执行发帖、评论、点赞、订阅或私信。
- 遇到 `AUTH_REQUIRED` 时，让用户在 Chrome 中刷新 Reddit 登录态。
- 不绕过验证码或风控。
