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
- 取证方式：仅 `scripts/elk_api_query.py`（Kibana API）；禁止 Playwright 页面查询 ELK。
- 目标：按时间升序定位首个 `phase=response hit=false` 的 `cmpId`。

## ES

- 仅当首次丢失在召回阶段时进入 ES。
- 进入 ES 前必须先按 `requestDsl/targetUrl` 解析控制台地址；若命中共享索引歧义，再用 `sourceSystem` 消歧，仍失败则直接阻断。
- 默认三步：`原DSL` -> `目标存在性` -> `去 text must 对照`。
- 字段不明确或 DSL 报错时再查 `_mapping`。
- 取证方式：仅 `scripts/es_proxy_query.py`；`sit/uat` 走 Kibana Dev Tools `console proxy`，`prod` 走中立云控制台 `requestEs`。禁止 Playwright 页面操作，禁止 `curl` 直连 ES。
- 生产环境没有 Kibana/ELK 查询 ES 实际内容的权限，不得把 prod ES 数据查询退回到 ELK 地址。

## 自动化注意事项

- 若浏览器 cookie 失效或代理接口返回未登录/无权限，先让用户在浏览器重新登录控制台，再重跑脚本。
- 多次执行 DSL 时，强制记录 `path/method/body` 与响应摘要，避免把不同查询结果混用。
- 若 prod 中立云 `request_proxy_url` 仍是占位，属于 skill 维护态未完成；可在维护阶段用 Playwright 抓 Network 后写入本地 `env-config.local.*`，正常排查阶段不得临时打开页面点击查询。
