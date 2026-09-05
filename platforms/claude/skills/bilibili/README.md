# bilibili

## 作用

只读访问 B站：搜索、热门、排行、视频详情、音频入口，以及通过 OpenCLI 读取字幕。

## 平台支持

- Claude（已支持）

## 工作原理

默认使用 `bilibili-cli` 包提供的 `bili` 命令，因为它覆盖搜索、热门、排行、视频详情和音频入口；搜索 API 作为无需安装的轻量兜底；OpenCLI 用于字幕和浏览器登录态增强。

## 前置条件

- `bili`（安装包为 `bilibili-cli`）：完整搜索/详情/热门/排行能力
- OpenCLI：字幕能力
- `video-transcribe`：完整转录、关键帧、图文笔记

安装依赖需要用户单独确认；本仓库不自动安装 `bilibili-cli` 或 OpenCLI。检查是否已安装时使用 `command -v bili`，不要把安装包名当作命令名。

## 验证命令

```bash
command -v bili
bili --version
command -v opencli
curl -s -A "Mozilla/5.0" "https://api.bilibili.com/x/web-interface/search/all/v2?keyword=test&page=1"
```

## 使用方式

```bash
bili search "AI 教程" --type video -n 5
bili hot -n 10
bili rank -n 10
bili video "BVxxxx"
bili audio "BVxxxx"
opencli bilibili subtitle "BVxxxx"
```

## 边界

- 不把 `yt-dlp` 作为 B站默认读取路线。
- 需要完整替代观看视频时，改用 `video-transcribe`。
