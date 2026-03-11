# 诊断规则

## 固定原则

- 优先用 `trace/recordInfo` 拿结构化链路，但先摘要化，不直接展开全文。
- 默认先做阶段定位并给出“目标在哪个阶段丢失”的结论。
- 如果是 live request，始终在请求体里注入 `traceTargetIds`，这样 ELK 才能按目标 ID 定位。
- ELK 默认时间窗用 `now-3d` 到 `now`，不默认向更早时间扩展。
- 查询 ELK 时，优先按 `targetId` 收敛，再加 `TRACE_TARGET_ES`、`cmpId`、`hit=true/false`，最后才加 `requestId`。
- 只有确认问题发生在检索阶段时才进入 ES 控制台。
- 文本召回阶段丢失时，默认进入 ES 做根因分析（复跑真实 DSL）。
- 文本阶段已能解释根因时，默认不继续展开向量阶段；仅在证据矛盾或用户明确要求时再查向量。
- 进入 ES 的补充前置条件：阶段证据不足以解释检索丢失原因时也应进入。
- `_explain` / `_analyze` 必须使用物理索引，不可直接对多索引 alias 执行。
- 如果问题已经明确发生在 `full_range_rerank` 或更后的准出阶段，就不要再查 ES。
- 若 3 天内没有 `TRACE_TARGET_ES`/trace 证据，先判定为“未复现”，要么构造带 `traceTargetIds` 的复现请求，要么让用户发送该请求后再继续排查。

## 文档链路

- `full_range_meta_filter`
  - 关注范围、权限、skill 过滤、来源系统过滤。
  - 若 `operateMsg` 已显示查无索引范围或元数据过滤后为空，可直接判为前置过滤问题。

- `full_range_docTxtRecall`
  - 这是文档文本召回主阶段。
  - 先找 ELK 里的 `TRACE_TARGET_ES`：
    - `phase=response hit=false` 说明目标不在该 ES 查询的返回集里。
    - `phase=response hit=true` 说明目标进入了该 ES 查询的返回集。
  - 若后续日志显示分数过滤、Dual TopN 或 `targetBefore/targetAfter` 变化，再继续细分为排序截断、分数过滤或 TopN 过滤。
  - 不要仅凭 `targetBefore=[] targetAfter=[]` 就断言原始 ES 没命中，这类日志可能已经发生在分数过滤之后。
  - 当 `keep filter + remove text must` 能命中、`keep filter + keep text must` 不能命中时，可直接判定为 query-text mismatch。
  - 仅在用户要求“为什么文本不匹配”时，再做 `_analyze` 命中块对比并输出最高命中条目。

- `recall_doc_vector_v3_filter`
  - 这是带特征过滤的 V3 文档向量召回。
  - 当文本召回证据不足，或者链路明显走了特征路由时，再看这一阶段。

- `doc_item_vector_retrieval_batch_es`
  - 这是文档项向量召回的 ES 直查阶段。
  - 若文本召回没找回目标，再看目标是否被向量召回补回。

- `full_range_rerank`
  - 这是全范围重排和最终权限复核阶段。
  - 如果目标在前面的召回阶段是 `hit=true`，但在这里之后消失，直接判为重排或准出阶段问题。
  - 此时不需要再去 ES 做检索验证。

## FAQ 链路

- `full_range_meta_filter`
  - 判定方式与文档一致。

- `full_range_faqTxtRecall`
  - 这是 FAQ 文本召回主阶段。
  - 优先看 ELK 中目标 ID 对应的 `TRACE_TARGET_ES` 和 `hit=true/false`。

- `recall_faq_vector_v3_filter`
  - 这是带特征过滤的 V3 FAQ 向量召回。

- `faq_vector_retrieval_batch_es`
  - 这是 FAQ 向量召回的 ES 直查阶段。
  - 要同时看 `TRACE_TARGET_ES phase=request` 和 `phase=response`：
    - 若 `phase=response hit=false`，再检查 `requestDsl` 的 `terms.knowledge_base_id` 是否包含目标 FAQ。
    - 若 `knowledge_base_id` 过滤列表不含目标 FAQ，可判定为上游候选集收敛导致目标未进入向量召回，不是该 ES 查询结果内被打分淘汰。
  - 若 ES 证据仍不足，再对同一用户和同一权限条件做一次“简化 query + FAQ-only”的对照复现：
    - 若对照请求能命中目标 FAQ，说明目标可召回，原始 query 属于检索意图/候选收敛问题。
    - 若对照请求仍完全不命中，再继续排查权限、索引覆盖或数据质量。

- `full_range_rerank`
  - FAQ 最终准出也会经过这里。
  - 一旦确认是在这里丢失，就停止 ES 深挖。

## ELK 查询优先级

1. `"<targetId>"`
2. `"<targetId>" and "TRACE_TARGET_ES"`
3. `"<targetId>" and "<cmpId>"`
4. `"<targetId>" and "hit=false"`
5. `"<targetId>" and "<requestId>"`

常用 `cmpId` 字符串：

- `full_range_meta_filter`
- `full_range_docTxtRecall`
- `full_range_faqTxtRecall`
- `recall_doc_vector_v3_filter`
- `doc_item_vector_retrieval_batch_es`
- `recall_faq_vector_v3_filter`
- `faq_vector_retrieval_batch_es`
- `full_range_rerank`

## 进入 ES 的条件

进入 ES 的默认场景：

- ELK 明确显示文本召回 `hit=false`
- ELK 明确显示向量召回 `hit=false`，且首个丢失阶段就是向量或用户明确要求向量根因
- ELK 显示目标在召回阶段命中，但怀疑被分数过滤、size 截断或 TopN 过滤掉

进入 ES 后，按这个顺序取证：

1. 复原原始 DSL
2. 文本召回先做存在性与对照：目标存在性查询 -> 原始 DSL -> `keep filter + remove text must` 对照
3. 若需要 `_explain` / `_analyze`，先拿目标 `_index`，再在物理索引执行
4. 向量召回仅在需要时复跑，并核对关键过滤（`skill_id`、`knowledge_base_id`）
5. 需要排序证据时再计算 `rank / score / threshold`
6. 用户要求完整文本存储时，导出不含向量的文本字段全集

## 停止条件

满足以下任意条件就停止继续展开：

- trace 已经明确显示目标在 `full_range_rerank` 或更后面丢失
- ELK 已有足够的 `hit=true/false` 证据支撑结论
- ES 已经给出明确的 `rank / score / threshold` 结论
