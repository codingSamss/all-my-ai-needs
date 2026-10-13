# xiaohongshu

## 作用

通过 OpenCLI 复用用户 Chrome 登录态，只读访问小红书：搜索笔记、读取笔记详情、评论、feed 与用户公开笔记，以及下载笔记媒体。

## 平台支持

- Claude（已支持）

## 工作原理

OpenCLI 使用本地 daemon + Chrome 扩展复用真实浏览器登录态。数据提取交给 OpenCLI，本 skill 不维护独立 HTTP/API 抓取、Chrome Cookie DB 直读或 `xhs-cli` 路线。

## 前置条件

- Node.js / npm；OpenCLI 1.8.8 要求 Node.js >=20.18.1
- 已评估版本的 `@jackwener/opencli`
- Chrome OpenCLI extension
- Chrome 已登录小红书

安装或升级前阅读 [版本与安全评估](references/opencli-upgrade.md)。1.8.8 的功能已核对，但其原始依赖存在安全公告，不能直接作为推荐安装版本。依赖安装按用户授权执行，本仓库不自动安装扩展或写入 Cookie。

## 验证命令

```bash
command -v opencli || true
node --version
opencli --version
opencli daemon status
```

注意：日常检查不要用 `opencli doctor`，它可能启动 daemon。

## 使用方式

```bash
opencli xiaohongshu search "咖啡机" -f yaml
opencli xiaohongshu note "<full_note_url_with_xsec_token>" -f yaml
opencli xiaohongshu comments "<full_note_url_with_xsec_token>" --limit 5 -f yaml
opencli xiaohongshu feed -f yaml
opencli xiaohongshu user "<user_id>" -f yaml
```

经单独评估且支持 1.8.8 筛选参数的安装，可使用：

```bash
opencli xiaohongshu search --help
opencli xiaohongshu search "咖啡机" --sort latest --note-type image --publish-time week --limit 5 -f yaml
```

旧版本不要直接套用新增参数。笔记与评论必须使用搜索、feed 或主页返回的完整签名链接。

## 边界

- 只读，不执行发帖、评论、点赞、收藏或关注。
- 遇到 `AUTH_REQUIRED` 时停止批次，让用户在 Chrome 中刷新小红书登录态。
- 遇到 `SECURITY_BLOCK`、验证码或账号警告时停止整个批次，不叠加外层重试。
- 批量串行执行并留间隔；默认关闭 trace，带签名的链接、manifest 与排障材料只留本地。
- 不绕过验证码或风控。
