# TRACE_TARGET_ES 真实格式样例

> 状态：已于 `2026-03-30` 在 prod 通过真实回放核对。
> 用途：只用于确认 ELK 日志格式、`targetUrl` 结构、`[cluster=N]` 路由优先级。执行仍以 `SKILL.md` 为准。

## 已核对事实

- `TRACE_TARGET_ES` 只会在 `traceTargetIds` 非空时打印。
- `phase=request` 日志会携带 `requestDsl=...`。
- `phase=response` 日志会携带 `isError/tookMs/returnedHitCount/totalHitCount`。
- `targetUrl` 真实格式为：

```text
GET /<index>
GET /<index1,index2>
GET /<index或索引列表> [cluster=N] (<desc>)
```

- 进入 ES 前，若 `targetUrl` 已带 `[cluster=N]`，应直接按该集群跳转，不再要求 `sourceSystem`。

## 样例 1：FAQ 文本召回 response

```text
event=TRACE_TARGET_ES phase=response requestId=<replayRequestId>
cmpId=full_range_faqTxtRecall
targetUrl=GET /iop_rag_flow_v3-faq-iop-knowledge-all [cluster=4] (V3-FAQ文本召回)
hit=false
targetIds=[<probeOrTargetId>]
isError=false
tookMs=10
returnedHitCount=0
totalHitCount=0
```

## 样例 2：向量召回 request

```text
event=TRACE_TARGET_ES phase=request requestId=<replayRequestId>
cmpId=doc_item_vector_retrieval_batch_es
targetUrl=GET /iop_rag_flow_v3-catalog-iop-knowledge-patent_search [cluster=5] (V3-向量召回KNN)
hit=false
targetIds=[<probeOrTargetId>]
requestDsl={...}
```

## 样例 3：多索引 targetUrl

```text
event=TRACE_TARGET_ES phase=request requestId=<replayRequestId>
cmpId=doc_item_vector_retrieval_batch_es
targetUrl=GET /iop_rag_flow_v3-catalog-iop-knowledge-shared,iop_rag_flow_v3-catalog-iop-knowledge-ihr-train [cluster=4] (V3-向量召回KNN)
hit=false
targetIds=[<probeOrTargetId>]
requestDsl={...}
```

## 格式核对建议

- 如果目标只是确认日志结构，而不是诊断某个具体 `docId/faqId`：
  - 可以回放原请求并临时注入一个探针 `traceTargetIds=["TRACE_FORMAT_PROBE_<ts>"]`
  - 然后用 `requestId + probeId + TRACE_TARGET_ES` 精确查 ELK
- 该探针结果只能证明：
  - `TRACE_TARGET_ES` 是否真的打印
  - `targetUrl` 是否带 `[cluster=N]`
  - `requestDsl`/response 关键字段是否完整
- 该探针结果不能替代真实目标召回诊断结论。
