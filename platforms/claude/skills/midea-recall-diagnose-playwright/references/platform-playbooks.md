# 平台操作手册

## 检索接口

- 优先使用浏览器登录态，而不是独立 token。
- 若页面出现登录态问题（密码/MFA/重登），先暂停并等待用户在当前标签页手动登录，登录完成后继续。
- 只有在“已确认登录成功”但浏览器访问仍持续受限（例如稳定 `403`）时，才启用终端 `curl` 直发：
  - `POST /rag-recall/api/search/keyword`
  - `GET /rag-recall/api/search/trace/recordInfo?linkId=<requestId>`
  - 请求头沿用用户给定的 `appId`/`appChannel`，并继续使用 ELK 页面做后续阶段取证。
- 若用户给的是完整请求体：
  - 先用 `scripts/prepare_diagnosis.py` 生成规范化输入。
  - 确保 `requestId` 已存在。
  - 确保 `traceTargetIds` 已包含所有目标 ID。
- 发送 live request 时，只保留必要的响应摘要：
  - `requestId`
  - 返回总数
  - 顶层错误信息

如果页面没有现成调用入口，优先在同域已登录页面里用 `browser_run_code` 或 `browser_evaluate` 发 `fetch` 请求，不要切到无登录态的外部命令。

## Trace 接口

- 优先访问 `GET /rag-recall/api/search/trace/recordInfo?linkId=<requestId>`。
- 默认只看这些字段：
  - `linkId`
  - `question`
  - `requestBody` 摘要
  - `stepList[].cmpId`
  - `stepList[].cmpName`
  - `stepList[].operateMsg`
  - `stepList[].timeSpent`
  - `detailList[].targetUrl`
  - `detailList[].error`
- 不要把完整 `responseBody` 拉进上下文。
- 若需要展开，先用 `scripts/compact_trace.py --expand-step <cmpId>` 做二次裁剪。

## ELK

- 默认时间窗使用 `now-3d` 到 `now`。
- 不要默认扩大到 3 天之外，除非用户明确要求。
- 优先用 `targetId` 检索，而不是 `requestId`。
- 先给阶段结论；若丢在文本/向量召回阶段，默认继续做根因分析。
- 常用 KQL 组合：
  - `"<targetId>"`
  - `"<targetId>" and "TRACE_TARGET_ES"`
  - `"<targetId>" and "full_range_docTxtRecall"`
  - `"<targetId>" and "full_range_faqTxtRecall"`
  - `"<targetId>" and "faq_vector_retrieval_batch_es"`
  - `"<targetId>" and "full_range_rerank"`
  - `"<targetId>" and "hit=false"`
- FAQ 漏召回时，优先取两条日志对比：
  - `cmpId=full_range_faqTxtRecall phase=request|response`
  - `cmpId=faq_vector_retrieval_batch_es phase=request|response`
- 重点看 `faq_vector_retrieval_batch_es phase=request` 里的 `requestDsl`：
  - 若 `terms.knowledge_base_id` 不包含目标 FAQ，则说明目标没进入向量候选集。
- 当 ELK 已明确某阶段 `hit=false` 时，先判定阶段，不要急着进 ES。
- 如果 3 天内没有 `TRACE_TARGET_ES` 或找不到对应 `requestId` 的 trace 证据，先判为“未用 trace 复现”，然后：
  - 用带 `traceTargetIds` 的请求重放一次，或
  - 明确让用户发一次带 `traceTargetIds` 的复现请求。

## ES 控制台

- 只在检索阶段问题时进入 ES；文本/向量召回丢失默认进入。
- 优先复用 trace 或 ELK 里已经出现的原始 DSL。
- 文本召回默认先做最短链路：目标存在性 -> 原始 DSL -> `keep filter + remove text must` 对照。
- 文本阶段已定因时，默认不继续展开向量阶段；只有用户明确要求或证据矛盾时再查向量。
- `_explain` / `_analyze` 必须在物理索引执行：
  - 先用 `_search` 拿目标 `_index`
  - 再执行 `/{index}/_explain/{id}` 或 `/{index}/_analyze`
- 先用原始 `size` 复跑，再把 `size` 拉大到 `10000` 看真实 rank（仅在需要排序证据时）。
- 默认输出：`total hits`、`returned hits`、目标 `rank/score`、阈值分数、关键过滤条件（如 `skill_id` / `knowledge_base_id`）。
- 仅在用户问“为什么排这么后”时，再追加 `_explain`；仅在用户问“为什么没匹配上”时，再按需追加 `_analyze` 命中块对比。
- 若用户要“目标文档文本召回相关完整存储”，默认导出不含向量的文本字段全集（`search_item_obj`、`content`、ID/权限/关系字段）。
- 如果页面上的响应编辑器会截断结果，优先改用：
  - 网络请求抓包
  - 浏览器内 `fetch`
  - 控制台代理接口的完整响应读取

## Playwright 注意事项

- 先拿快照，再引用元素 ref。
- 页面跳转、切 tab、展开面板后要重新快照。
- 页面 UI 展示的 JSON 可能被截断；这类场景优先用 `browser_run_code` 或网络抓取完整数据。
- 发起多次查询时，要校验“响应是否对应当前请求”（例如检查路径关键字、响应结构签名），避免读取到上一条结果。
- 浏览器自动化的目标是拿证据，不是还原 UI 操作本身。能直接抓请求体或响应体时，优先抓数据。
