import type { Compaction, Ctx } from '../types'

const validCount = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0

export function tokenText(value: number): string {
  if (value < 1000) return String(Math.round(value))
  if (value < 10000) return `${Number((value / 1000).toFixed(1))}k`
  if (value < 1e6) return `${Math.round(value / 1000)}k`
  return `${Number((value / 1e6).toFixed(1))}M`
}

export function compactionState(breakdown?: {
  isAutoCompactEnabled?: boolean; autoCompactThreshold?: number; totalTokens?: number
}): Compaction {
  // 只接受引擎已经解析的触发阈值，不把模型容量或本机设置当作会话阈值。
  return {
    enabled: typeof breakdown?.isAutoCompactEnabled === 'boolean' ? breakdown.isAutoCompactEnabled : null,
    threshold: validCount(breakdown?.autoCompactThreshold) && breakdown.autoCompactThreshold > 0
      ? breakdown.autoCompactThreshold : null,
    used: validCount(breakdown?.totalTokens) ? breakdown.totalTokens : null,
  }
}

export function contextProgress(context: Ctx | null, compaction: Compaction) {
  // 与 /context 的本地统计同口径，包含回复及新增消息；不是仅上次请求的输入 token。
  const used = compaction.used
  const threshold = compaction.threshold
  if (compaction.enabled === true && threshold !== null && validCount(threshold) && threshold > 0) {
    if (!validCount(used)) return { label: '压缩 —', detail: ` 阈值${tokenText(threshold)} · 用量待更新`, percent: null, ratio: null }
    // 不提前四舍五入到 100%；达到阈值也只表示接近下一次压缩检查，不宣称已经执行。
    const percent = Math.floor(used / threshold * 1000) / 10
    const remaining = Math.max(0, threshold - used)
    const ratio = `${tokenText(used)}/${tokenText(threshold)}`
    return { label: `压缩${percent}%`,
      detail: ` ${ratio}${remaining > 0 ? '' : ' · 已达压缩线'}`,
      percent, ratio }
  }
  const percent = validCount(context?.percent) ? context.percent : null
  const tokens = validCount(context?.tokens) && validCount(context?.window) && context.window > 0
    ? ` ${tokenText(context.tokens)}/${tokenText(context.window)}` : ''
  // 关闭、旧宿主缺字段和读取失败都明确降级，绝不继续展示上一次的压缩进度。
  return { label: percent === null ? 'ctx —' : `ctx${percent}%`,
    detail: `${tokens} · ${compaction.enabled === false ? '自动压缩已关' : '压缩阈值未知'}`, percent: null, ratio: null }
}
