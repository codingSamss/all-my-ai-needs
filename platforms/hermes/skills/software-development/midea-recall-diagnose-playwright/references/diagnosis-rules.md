# 诊断规则（精简版）

> 说明：本文件为辅助摘要，冲突时以 `SKILL.md` 为准。

## 固定原则

- 先阶段定位，再根因细化。
- 首次丢失阶段定义：按时间升序找到第一个 `phase=response hit=false` 的 `cmpId`。
- 有完整请求必须先回放，再查 ELK。
- 回放后必须 requestId-first，禁止先 broad search。
- 首条 KQL 必须是 `requestId + targetId + TRACE_TARGET_ES` 精确匹配，禁止 `*` 通配与降级查询。
- `TRACE_TARGET_ES` 只会在 `traceTargetIds` 非空时出现；若原始请求 `traceTargetIds=[]`，优先判定为“未完成带 trace 的复现”，应回放并注入 `targetIds`。
- ELK/ES 取证仅允许 Playwright 页面操作；禁止 `curl` 直连（`keyword` 回放除外）。
- 仅召回阶段问题进入 ES。
- ES 取证前必须先按 `requestDsl/targetUrl` 解析到唯一控制台地址；若命中共享索引歧义，可再用 `sourceSystem` 消歧，仍失败则阻断。
- 真实格式已核对：`phase=request` 带 `requestDsl=...`；`phase=response` 带 `isError/tookMs/returnedHitCount/totalHitCount`；`targetUrl` 带 `[cluster=N]` 时优先按集群路由。
- 首次丢失必须按链路顺序判定（优先 CHAIN_NAME，其次关键链路代码动态解析）；未验证文本阶段证据时，禁止直接判向量阶段。
- 输出前必须补齐最小代码证据（至少 2 条 `文件:行号`）。

## ELK 最小查询顺序

1. `"<requestId>" and "<targetId>" and "TRACE_TARGET_ES"`
2. `"<requestId>" and "<targetId>" and "<cmpId>"`
3. `"<requestId>" and "<targetId>" and "hit=false"`

## ES 最小取证

0. `requestDsl/targetUrl -> index -> cluster -> esConsoleRoute` 解析成功
1. 原始 `requestDsl` 复跑
2. 目标存在性查询（DOC: `doc_id`; FAQ: `knowledge_base_id`）
3. `keep filter + remove text must` 对照（仅文本阶段）

## 快速判定

- `存在性=0`：索引缺数据/发布未生效/索引路由不覆盖
- `存在性>0 且 原DSL=0`：文本匹配或过滤条件问题
- `原DSL>0 但最终未返回`：排序/阈值/TopN 问题
