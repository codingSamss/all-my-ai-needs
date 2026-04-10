# Quick Runbook（唯一推荐路径）

## 一句话原则

- 有完整请求就先回放拿 replay `requestId`；回放后一律 `requestId + TRACE_TARGET_ES + targetId` 查 ELK，禁止先 broad search。
- 原始请求若 `traceTargetIds=[]`，原 `requestId` 通常不会有 `TRACE_TARGET_ES`；必须回放并注入 `targetIds`。

## ELK 查询顺序

1. `"<requestId>" and "<targetId>" and "TRACE_TARGET_ES"`
2. `"<requestId>" and "<targetId>" and "<cmpId>"`
3. `"<requestId>" and "<targetId>" and "hit=false"`

- 执行通道：ELK 查询只用 Playwright，禁止 `curl` 直连。
- 首条查询必须完整精确匹配，禁止通配符（如 `replay_*`）。

## 时间窗

- 第一轮：回放时间点 `±15 分钟`
- 第二轮：`now-3d ~ now`
- 不默认扩大到 3 天之外。

## ES 三步快检（仅召回阶段）

0. 先看 `targetUrl` 是否带 `[cluster=...]`；有则直接按集群跳转。没有再按 `requestDsl/targetUrl` 提取实际索引路由；若命中共享索引歧义，再用 `sourceSystem` 消歧
1. 原始 `requestDsl` 复跑
2. 目标存在性查询（DOC: `doc_id`；FAQ: `knowledge_base_id`）
3. 保留 filter + 去掉 text must（仅文本阶段）

## TRACE 真实格式

- 已于 `2026-03-30` 在 prod 回放核对：`phase=request` 日志带 `requestDsl=...`，`phase=response` 日志带 `isError/tookMs/returnedHitCount/totalHitCount`。
- `targetUrl` 真实格式为：`GET /<index或逗号分隔索引> [cluster=N] (<desc>)`。
- 仅做格式核对时，可回放并注入探针 `traceTargetIds=["TRACE_FORMAT_PROBE_<ts>"]`；该探针只能验证日志结构与集群路由，不能当作目标命中证据。
- 样例见 `references/trace-target-es-format.md`。

## 首次丢失判定门禁

- 顺序来源优先级：`CHAIN_NAME` 实际链路 > 关键链路代码动态解析（`SearchLiteFlowService + LiteFlowConstants`）> 默认顺序。
- 禁止在未验证文本阶段证据时直接判“向量阶段首次丢失”。
- 结论前必须执行：

```bash
python3 scripts/first_loss_guard.py \
  --target-type <DOC|FAQ|MIXED> \
  --chain-line '<CHAIN_NAME日志行>' \
  --events '<events-json>'
```

- 如果没有 `CHAIN_NAME`，改用代码动态解析：

```bash
python3 scripts/first_loss_guard.py \
  --target-type <DOC|FAQ|MIXED> \
  --repo-root '<rag-recall-root>' \
  --chain-id '_FULL_RANGE_SEARCH_WITH_LLM_' \
  --events '<events-json>'
```

## 禁止事项

- 不要调用 `trace/recordInfo`
- 不要先用 `targetId` 扫 3 天
- 不要一上来全量读代码
- 不要用 `curl` 查询 ELK/ES（仅 `keyword` 回放允许 `curl`）
- 不要把首条 KQL 从三元组降级为 requestId-only 或 targetId-only
- 不要在 `requestDsl` 未提供唯一索引且又没有可用 `sourceSystem` 消歧时继续执行 ES 查询
