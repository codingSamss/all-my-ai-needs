# xiaohongshu

## 作用

通过 OpenCLI 复用用户 Chrome 登录态，只读访问小红书：搜索笔记、读取笔记详情、评论、feed 与用户公开笔记。

## 平台支持

- Claude（已支持）

## 工作原理

OpenCLI 使用本地 daemon + Chrome 扩展复用真实浏览器登录态。这个 skill 不再保留 HTTP/API、Chrome Cookie DB 直读、SSR 解析或 `xhs-cli` 路线。

## 前置条件

- Node.js / npm
- `@jackwener/opencli`
- Chrome OpenCLI extension
- Chrome 已登录小红书

安装依赖需要用户单独确认；本仓库不自动安装 OpenCLI、浏览器扩展或写入 Cookie。

## 验证命令

```bash
command -v opencli || true
opencli daemon status
```

注意：日常检查不要用 `opencli doctor`，它可能启动 daemon。

## 使用方式

```bash
opencli xiaohongshu search "咖啡机" -f yaml
opencli xiaohongshu note "https://www.xiaohongshu.com/explore/..." -f yaml
opencli xiaohongshu comments "<note_id>" -f yaml
opencli xiaohongshu feed -f yaml
opencli xiaohongshu user "<user_id>" -f yaml
```

## 边界

- 只读，不执行发帖、评论、点赞、收藏或关注。
- 遇到 `AUTH_REQUIRED` 时，让用户在 Chrome 中刷新小红书登录态。
- 不绕过验证码或风控。
