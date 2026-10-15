import { atom, read, update } from 'claude-code'
import type { Register, SessionContextUsage, EngineInterface } from 'claude-code'
import type { Mood, PanelState, FooterState, Ctx, WorkState } from '../types'
import { pixelIconSvg, pixelMeterSvg, pixelPercentSvg } from './quota-pixels'
import { pixelLabelSvg, pixelQuotaCardSvg } from './quota-text'
import { DONE_SECONDS, SCENE_HEIGHT, SCENE_WIDTH, sceneSvg } from './scene'
import { emptyWork, finished, hasWork, reconcile, workStamp, started, notificationTask, panelWork } from './background'

// 本文件按显示需求独立实现；动画绘图使用包内 MIT 授权素材。
// 面板与秒级倒计时分开订阅，cache 更新不能让宠物 SVG 被反复替换。
const panel = atom({ plugin: 'pixel-buddy-sam', key: 'panel' } as const, {
  phase: 'idle', phaseAt: 0, clockAt: 0, limits: [], work: emptyWork(0),
} as PanelState)
const footer = atom({ plugin: 'pixel-buddy-sam', key: 'footer' } as const, {
  clockAt: 0, cacheAt: null, context: null,
} as FooterState)
const GREEN = '#4cc35a', AMBER = '#e5a33a', RED = '#e5534b', NEUTRAL = '#9a9a9a'

const usedColor = (used: number) => used >= 90 ? RED : used >= 70 ? AMBER : GREEN
const tokenText = (value: number) => value < 1e6
  ? `${Math.round(value / 1000)}k`
  : `${(value / 1e6).toFixed(1).replace(/\.0$/, '')}M`

function resetText(iso: string | undefined, now: number): string {
  const until = iso ? Date.parse(iso) : NaN
  if (!now || !Number.isFinite(until)) return '重置时间待更新'
  const total = Math.max(0, Math.round((until - now) / 60000))
  const days = Math.floor(total / 1440), hours = Math.floor((total % 1440) / 60), minutes = total % 60
  const duration = days ? `${days}天${hours ? `${hours}小时` : ''}`
    : hours ? `${hours}小时${minutes ? `${minutes}分` : ''}` : `${minutes}分`
  return `${duration}后重置`
}

function scenePhase(phase: Mood, elapsed: number): [Mood, number] {
  // 完成动画按时间衔接，不依赖一次性回调，避免重载后丢失转换。
  if (phase === 'done') {
    if (elapsed < DONE_SECONDS) return ['done', elapsed]
    return scenePhase('relax', elapsed - DONE_SECONDS)
  }
  return phase === 'relax' && elapsed >= 240 ? ['idle', elapsed - 240] : [phase, elapsed]
}

function contextState(context: SessionContextUsage, compactWindow?: number): Ctx {
  // 只保留读数，不把 summary 中的文件、工具与分类明细写进状态。
  return { tokens: context.tokens, window: context.window, percent: context.percent, compactWindow }
}

function effectiveWindow(context: SessionContextUsage): number | undefined {
  const details = context.breakdown
  const value = details?.rawMaxTokens
  // 让宿主处理模型级设置、环境变量和启动参数的优先级；无有效读数则退回模型窗口。
  return details?.isAutoCompactEnabled !== false && typeof value === 'number'
    && Number.isFinite(value) && value > 0 && value < context.window ? value : undefined
}

async function changeWork($: EngineInterface, epoch: number, apply: (work: WorkState) => WorkState) {
  const now = await $.clock.now()
  await update($, panel, state => {
    // 重载、换会话后的旧 Promise 只能结束自己，不能污染新会话的状态。
    const previous = panelWork(state)
    if (previous.epoch !== epoch) return state
    const work = apply(previous)
    const resting = hasWork(previous) && !hasWork(work) && work.known
    return { ...state, work, ...(resting ? { phase: 'relax' as const, phaseAt: now, clockAt: now } : {}) }
  })
}
async function closeTask($: EngineInterface, id: string) {
  const at = workStamp(), work = panelWork(await read($, panel))
  await changeWork($, work.epoch, current => finished(current, id, at))
}

async function snapshotWork($: EngineInterface, tasks: unknown) {
  const at = workStamp(), work = panelWork(await read($, panel))
  await changeWork($, work.epoch, current => reconcile(current, tasks, at))
}


export const register: Register = (on, options) => {
  const ttl = options.cacheTtl === '5m' ? 300000 : 3600000
  on('tool.call', async ($, event, next) => {
    if (event.tool !== 'Bash' && event.tool !== 'Agent') return next(event)
    const at = workStamp(), work = panelWork(await read($, panel))
    const call = `call:${event.tool_use_id}`
    await changeWork($, work.epoch, current => at < current.epoch ? current : {
      ...current, calls: { ...current.calls, [call]: at },
    })
    try {
      const result = await next(event)
      if (event.tool === 'Bash' && !result.deny && !result.isError) {
        const output = result.result as { backgroundTaskId?: string; backgroundEndsWithFinalResponse?: true }
        // 随同步子代理最终回复被清理的 shell 不会再发通知，不能留下永久等待项。
        if (output?.backgroundTaskId && !output.backgroundEndsWithFinalResponse) {
          await changeWork($, work.epoch, current => started(current, output.backgroundTaskId, at))
        }
      }
      return result
    } finally {
      await changeWork($, work.epoch, current => {
        if (current.calls[call] !== at) return current
        const calls = { ...current.calls }; delete calls[call]
        return { ...current, calls }
      })
    }
  })

  on('agent.spawn', async ($, event, next) => {
    const at = workStamp(), work = panelWork(await read($, panel))
    const result = await next(event)
    if ('agentId' in result) await changeWork($, work.epoch, current => started(current, result.agentId, at))
    return result
  })
  on('tool.call', { tool: 'TaskStop' }, async ($, event, next) => {
    const work = panelWork(await read($, panel))
    const result = await next(event)
    if (!result.deny && !result.isError) {
      const at = workStamp()
      // 输入可以是 agent 名称；只有成功结果返回的规范 task_id 才用于结束跟踪。
      await changeWork($, work.epoch, current => finished(current, result.result?.task_id, at))
    }
    return result
  })
  // Mod 编译器要求事件名为字面量，两个入口共用同一套快照归并。
  on('classic.Stop', async ($, event, next) => {
    await snapshotWork($, event.background_tasks)
    return next(event)
  })
  on('classic.SubagentStop', async ($, event, next) => {
    await snapshotWork($, event.background_tasks)
    return next(event)
  })
  on('prompt.submit', async ($, event, next) => {
    if (event.origin.kind === 'task-notification') {
      const id = notificationTask(event.text)
      if (id) await closeTask($, id)
    }
    return next(event)
  })
  on('session.append', async ($, event, next) => {
    if (event.origin.kind === 'task-notification') {
      const text = event.message.content.filter(block => block.type === 'text').map(block => block.text).join('\n')
      const id = notificationTask(text)
      if (id) await closeTask($, id)
    }
    return next(event)
  })


  on('session.start', async ($, event, next) => {
    const epoch = workStamp()
    // summary 只做本地估算，不调用计数 API；这里只取有效窗口，分子仍用响应的真实 token。
    const usage = await $.session.usage({ breakdown: 'summary' }).catch(() => $.session.usage())
    const now = await $.clock.now()
    await update($, panel, () => ({
      phase: 'idle', phaseAt: now, clockAt: now, limits: usage.rateLimits, work: emptyWork(epoch),
    }))
    await update($, footer, () => ({ clockAt: now, cacheAt: null, context: contextState(usage.context, effectiveWindow(usage.context)) }))
    // 动画交给 SVG 内的 SMIL；这里只按分钟刷新额度文案，并补偿重载后丢失的阶段回调。
    $.clock.every(60000, async () => {
      const tick = await $.clock.now()
      await update($, panel, state => ({ ...state, clockAt: tick }))
    })
    $.clock.every(1000, async () => {
      const tick = await $.clock.now()
      const previous = await read($, footer)
      const warm = previous.cacheAt !== null && tick - previous.cacheAt < ttl + 2000
      if (warm) {
        await update($, footer, state => ({ ...state, clockAt: tick }))
      }
    })
    return next(event)
  })

  on('session.measure', async ($, event, next) => {
    const tick = await $.clock.now()
    const previousPanel = await read($, panel)
    const previousFooter = await read($, footer)
    let compactWindow = previousFooter.context?.compactWindow
    // 仅上下文变化时更新窗口；额度变化和秒级倒计时都不反复计算 summary。
    if (event.changed.includes('context')) {
      const usage = await $.session.usage({ breakdown: 'summary' }).catch(() => null)
      compactWindow = usage ? effectiveWindow(usage.context) : undefined
    }
    // 宿主重复发送相同额度时不重绘上方区域；context 和 cache 只影响底栏。
    if (event.rateLimits.length && JSON.stringify(event.rateLimits) !== JSON.stringify(previousPanel.limits)) {
      await update($, panel, state => ({ ...state, limits: event.rateLimits, clockAt: tick }))
    }
    await update($, footer, previous => ({
      ...previous, context: contextState(event.context, compactWindow),
      cacheAt: event.changed.includes('context') ? tick : previous.cacheAt,
      clockAt: tick,
    }))
    return next(event)
  })
  on('turn.start', async ($, event, next) => {
    if (event.agentId) return next(event)
    const at = workStamp()
    const tick = await $.clock.now()
    await update($, panel, state => at < panelWork(state).epoch ? state : ({ ...state, phase: 'working', phaseAt: tick, clockAt: tick,
      work: { ...panelWork(state), turnAt: at },
    }))
    return next(event)
  })
  on('turn.complete', async ($, event, next) => {
    const at = workStamp()
    if (event.agentId) {
      const tick = await $.clock.now()
      await update($, panel, state => {
        const previous = panelWork(state)
        if (at < previous.epoch) return state
        const work = finished(previous, event.agentId, at)
        const resting = hasWork(previous) && !hasWork(work) && work.known
        return { ...state, work, ...(resting ? { phase: 'relax' as const, phaseAt: tick, clockAt: tick } : {}) }
      })
    } else {
      const tick = await $.clock.now()
      await update($, panel, state => {
        const previous = panelWork(state)
        if (at < previous.epoch) return state
        const failed = event.isAborted || event.reason === 'error' || event.reason === 'refusal'
        // 没有这一轮的完整 Stop 快照时不能宣告全局完成；中断也不等于后台任务终止。
        const work = failed || !previous.snapshot || previous.snapshot < previous.turnAt
          ? reconcile(previous, undefined, at) : previous
        const phase = !failed && work.known && !hasWork(work) ? 'done' : 'idle'
        return { ...state, work, phase, phaseAt: tick, clockAt: tick }
      })
      if ((await read($, panel)).phase === 'done') {
        for (const delay of [DONE_SECONDS * 1000, (DONE_SECONDS + 240) * 1000]) {
          $.clock.after(delay, async () => {
            const current = await read($, panel)
            // 已开始新一轮任务时，旧庆祝计时器不能重绘或覆盖新阶段。
            if (current.phase !== 'done' || current.phaseAt !== tick) return
            const now = await $.clock.now()
            await update($, panel, state => ({ ...state, clockAt: now }))
          })
        }
      }
    }
    return next(event)
  })
  on('session.end', async ($, event, next) => {
    const epoch = workStamp()
    await update($, panel, state => ({ ...state, work: emptyWork(epoch) }))
    return next(event)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, event, next) => {
    if (event.props.hasSurvey) return next(event)
    const { Box, Text } = $.ui.resolve(event)
    const state = await read($, panel)
    const items = ([['five_hour', '5h', 'clock'], ['seven_day', '7d', 'cal']] as const).map(([kind, title, icon]) => {
      const limit = state.limits.find(item => item.kind === kind)
      // 未知用量保持未知；剩余额度与上下文占用比例使用不同含义的颜色规则。
      const remaining = limit && Number.isFinite(limit.percentUsed)
        ? Math.max(0, Math.min(100, 100 - limit.percentUsed)) : undefined
      return { kind, title, icon, remaining, reset: resetText(limit?.resetsAt, state.clockAt),
        color: remaining === undefined ? NEUTRAL : usedColor(100 - remaining),
        label: remaining === undefined ? '剩余 —' : `剩余${Math.round(remaining)}%` }
    })
    if (event.surface !== 'desktop' && event.surface !== 'vscode') {
      return <Box><Text dimColor>{items.map(item => `${item.title} ${item.label}`).join('   ')}</Text></Box>
    }
    const { Svg } = $.ui.resolve(event as typeof event & { surface: 'desktop' })
    const label = (text: string) => {
      const bitmap = pixelLabelSvg(text)
      return bitmap ? <Svg source={bitmap.source} width={bitmap.width} height={bitmap.height} alt={text} />
        : <Text dimColor wrap="truncate-end">{text}</Text>
    }
    const work = panelWork(state)
    const phase: Mood = hasWork(work) ? 'waiting' : event.props.isWorking ? 'working'
      : !work.known ? 'unknown' : state.phase === 'working' ? 'idle' : state.phase
    const [shown] = scenePhase(phase, Math.max(0, (state.clockAt - state.phaseAt) / 1000))
    return <Box flexDirection="row" alignItems="center" justifyContent="space-between" flexWrap="nowrap" columnGap={2} paddingX={1} overflow="hidden">
      <Box flexDirection="row" alignItems="center" flexShrink={0} columnGap={2}>
        {items.map(item => {
          const card = pixelQuotaCardSvg(`${item.title}·剩余`, item.remaining, item.reset, item.color)
          return <Box key={item.kind} flexDirection="row" alignItems="center" flexShrink={0} gap={0.75}>
            <Svg source={pixelIconSvg(item.icon)} width={18} height={18} alt={`${item.title} quota window`} />
            {card ? <Svg source={card.source} width={card.width} height={card.height} alt={`${item.title} ${item.label} ${item.reset}`} />
              : <Box flexDirection="column" flexShrink={0} rowGap={1}>
                <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap={1}>
                  {label(`${item.title}·剩余`)}
                  <Svg source={pixelPercentSvg(item.remaining, item.color)} width={64} height={16} alt={item.label} />
                </Box>
                <Svg source={pixelMeterSvg(item.remaining, item.color)} width={112} height={10} alt={item.label} />
                {label(item.reset)}
              </Box>}
          </Box>
        })}
      </Box>
      <Box flexGrow={1} flexShrink={1} width={0} minWidth={0} overflow="hidden" alignItems="center">
        <Box flexShrink={0}>
          <Svg source={sceneSvg(shown)} isInteractive width={SCENE_WIDTH} height={SCENE_HEIGHT}
            alt={shown === 'waiting' ? 'Claude is waiting for scripts or subagents'
              : shown === 'unknown' ? 'Claude task status is unknown'
              : `Claude is ${shown === 'done' ? 'celebrating' : shown === 'relax' ? 'relaxing' : shown}`} />
        </Box>
      </Box>
    </Box>
  })

  on('ui.render', { component: 'SessionMode' }, async ($, event) => {
    const { Box, Text } = $.ui.resolve(event)
    const state = await read($, footer)
    const left = state.cacheAt === null ? 0 : ttl - (state.clockAt - state.cacheAt)
    const seconds = Math.max(0, Math.ceil(left / 1000))
    const cache = state.cacheAt === null ? 'cache 待更新' : left <= 0 ? 'cache cold'
      : `cache ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
    const cacheColor = left <= 0 ? undefined : left < 60000 ? AMBER : GREEN
    const compactWindow = state.context?.compactWindow
    const isCompact = typeof compactWindow === 'number' && compactWindow > 0 && compactWindow < (state.context?.window ?? 0)
    const window = isCompact ? compactWindow : state.context?.window
    const tokenCount = state.context?.tokens
    const validTokens = typeof tokenCount === 'number' && Number.isFinite(tokenCount) && tokenCount >= 0
    // 百分比、分母和高亮必须采用同一窗口；不把模型占用率直接套在压缩窗口上。
    const percent = isCompact ? (validTokens ? Math.round(tokenCount / compactWindow * 100) : undefined) : state.context?.percent
    const known = typeof percent === 'number' && Number.isFinite(percent)
    const label = isCompact ? '' : 'ctx'
    const context = known ? `${label}${percent}%` : `${label} 待更新`
    const tokens = known && validTokens && window ? ` ${tokenText(tokenCount)}/${tokenText(window)}` : ''
    const modes = event.props.modes.join(' & ')
    // 首轮没有响应或响应前中断时，宿主没有用量；不要用横杠或 0 冒充读数。
    if (!known && state.cacheAt === null) {
      return <Text dimColor>{['cache / ctx 待首轮响应', modes].filter(Boolean).join(' · ')}</Text>
    }
    if (event.surface !== 'desktop' && event.surface !== 'vscode') {
      return <Text dimColor>{[cache, context + tokens, modes].filter(Boolean).join('  ·  ')}</Text>
    }
    // Desktop 会截断整个 SessionMode 槽，子元素换行无法扩宽；省略压缩标签，为完整分母留空间。
    return <Box flexDirection="row" alignItems="center" justifyContent="flex-end" flexWrap="wrap" minWidth={0} columnGap={1}>
      <Box flexShrink={0}><Text wrap="wrap" color={cacheColor} dimColor={left <= 0}>{cache + ' '}</Text></Box>
      <Box flexShrink={0}><Text wrap="wrap" color={known ? usedColor(percent) : undefined} dimColor={!known}>{context}</Text></Box>
      {tokens ? <Box flexShrink={0}><Text wrap="wrap" dimColor>{tokens}</Text></Box> : null}
      {modes ? <Text wrap="wrap" dimColor>{`· ${modes}`}</Text> : null}
    </Box>
  })
}
