# 平台操作手册（精简版）

> 说明：本文件是辅助说明，执行以 `SKILL.md` 为准。

## 环境分流

- `sit/uat`：优先本地复现 + 本地日志；证据不足再用 ELK/ES。
- `prod`：
  - 有完整请求：先回放拿 replay `requestId`，再 ELK/ES。
  - 只有 `requestId`：直接 requestId-first 查 ELK。

## 检索接口

- 回放统一用终端：`POST /rag-recall/api/search/keyword`。
- 禁止浏览器地址栏访问 `keyword`（会变成 `GET`）。
- 禁止调用 `trace/recordInfo`，避免口径冲突。
- 若原始请求日志里只有 `body.appId` 没有 `headers.appId`，允许用 `body.appId` 回填回放头；`appChannel` 同理。

## ELK

- 回放后第一条查询必须含：`requestId + targetId + TRACE_TARGET_ES`。
- `TRACE_TARGET_ES` 只会在 `traceTargetIds` 非空时打印；原始请求若 `traceTargetIds=[]`，要准备回放注入。
- 时间窗：先 `±15 分钟`，再 `now-3d~now`。
- 禁止先用 `targetId` 单独 broad search。
- 取证方式：仅 Playwright 页面操作；禁止 `curl`/脚本直连 ELK。
- 目标：按时间升序定位首个 `phase=response hit=false` 的 `cmpId`。

## ES

- 仅当首次丢失在召回阶段时进入 ES。
- 进入 ES 前必须先按 `requestDsl/targetUrl` 解析控制台地址；若命中共享索引歧义，再用 `sourceSystem` 消歧，仍失败则直接阻断。
- 默认三步：`原DSL` -> `目标存在性` -> `去 text must 对照`。
- 字段不明确或 DSL 报错时再查 `_mapping`。
- 取证方式：仅 Playwright 页面操作；禁止 `curl` 直连 ES。

## 自动化注意事项

- 页面跳转/切 tab 后重新快照。
- 多次执行 DSL 时，强制 `清空输入 -> 清空输出 -> 执行 -> 校验响应签名`。
