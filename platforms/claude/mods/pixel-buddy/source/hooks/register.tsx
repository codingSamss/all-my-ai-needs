import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'
import type { Mood, PanelState, FooterState } from '../types'
import { pixelIconSvg, pixelMeterSvg, pixelPercentSvg } from './quota-pixels'
import { pixelLabelSvg, pixelQuotaCardSvg } from './quota-text'
import { DONE_SECONDS, SCENE_HEIGHT, SCENE_WIDTH, sceneSvg } from './scene'

// 本文件按显示需求独立实现；动画绘图使用包内 MIT 授权素材。
// 面板与秒级倒计时分开订阅，cache 更新不能让宠物 SVG 被反复替换。
const panel = atom({ plugin: 'pixel-buddy-sam', key: 'panel' } as const, {
  phase: 'idle', phaseAt: 0, clockAt: 0, limits: [],
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

function contextSvg(percent: number): string {
  const active = Math.max(0, Math.min(10, Math.round(percent / 10)))
  const blocks = Array.from({ length: 10 }, (_, index) =>
    `<rect x="${index * 4}" y="0" width="3" height="8" fill="${index < active ? usedColor(percent) : '#3a3a3a'}"/>`).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 39 8" width="39" height="8" shape-rendering="crispEdges">${blocks}</svg>`
}

export const register: Register = (on, options) => {
  const ttl = options.cacheTtl === '5m' ? 300000 : 3600000

  on('session.start', async ($, event, next) => {
    // 用量只从宿主读取一次；后续使用 measure 事件。计时器不会轮询账号接口。
    const usage = await $.session.usage()
    const now = await $.clock.now()
    await update($, panel, () => ({
      phase: 'idle', phaseAt: now, clockAt: now, limits: usage.rateLimits,
    }))
    await update($, footer, () => ({ clockAt: now, cacheAt: null, context: usage.context }))
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
    // 宿主重复发送相同额度时不重绘上方区域；context 和 cache 只影响底栏。
    if (event.rateLimits.length && JSON.stringify(event.rateLimits) !== JSON.stringify(previousPanel.limits)) {
      await update($, panel, state => ({ ...state, limits: event.rateLimits, clockAt: tick }))
    }
    await update($, footer, previous => ({
      ...previous, context: event.context,
      cacheAt: event.changed.includes('context') ? tick : previous.cacheAt,
      clockAt: tick,
    }))
    return next(event)
  })
  on('turn.start', async ($, event, next) => {
    if (event.agentId) return next(event)
    const tick = await $.clock.now()
    await update($, panel, state => ({ ...state, phase: 'working', phaseAt: tick, clockAt: tick }))
    return next(event)
  })
  on('turn.complete', async ($, event, next) => {
    if (!event.agentId) {
      const tick = await $.clock.now()
      const phase = event.isAborted || event.reason === 'error' ? 'idle' : 'done'
      await update($, panel, state => ({ ...state,
        phase, phaseAt: tick, clockAt: tick,
      }))
      if (phase === 'done') {
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
    const phase: Mood = event.props.isWorking ? 'working' : state.phase === 'working' ? 'idle' : state.phase
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
            alt={`Claude is ${shown === 'done' ? 'celebrating' : shown === 'relax' ? 'relaxing' : shown}`} />
        </Box>
      </Box>
    </Box>
  })

  on('ui.render', { component: 'SessionMode' }, async ($, event, next) => {
    const { Box, Text } = $.ui.resolve(event)
    const state = await read($, footer)
    const left = state.cacheAt === null ? 0 : ttl - (state.clockAt - state.cacheAt)
    const seconds = Math.max(0, Math.ceil(left / 1000))
    const cache = state.cacheAt === null ? 'cache –' : left <= 0 ? 'cache cold'
      : `cache ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
    const cacheColor = left <= 0 ? undefined : left < 60000 ? AMBER : GREEN
    const percent = state.context?.percent
    const known = typeof percent === 'number' && Number.isFinite(percent)
    const context = known ? `ctx${percent}%` : 'ctx –'
    const tokens = known && state.context?.tokens ? ` ${tokenText(state.context.tokens)}/${tokenText(state.context.window)}` : ''
    const modes = event.props.modes.join(' & ')
    if (event.surface !== 'desktop' && event.surface !== 'vscode') {
      return <Text dimColor>{[cache, context + tokens, modes].filter(Boolean).join('  ·  ')}</Text>
    }
    const { Svg } = $.ui.resolve(event as typeof event & { surface: 'desktop' })
    return <Box flexDirection="row" alignItems="center" gap={1}>
      <Svg source={pixelIconSvg('clock')} width={14} height={18} alt="prompt cache timer" />
      <Text color={cacheColor} dimColor={left <= 0}>{cache}</Text>
      <Text dimColor>·</Text>
      <Svg source={contextSvg(known ? percent : 0)} width={39} height={8} alt="context used" />
      <Text><Text color={known ? usedColor(percent) : undefined} dimColor={!known}>{context}</Text>
        {tokens ? <Text dimColor>{tokens}</Text> : null}</Text>
      {modes ? <Text dimColor>{`· ${modes}`}</Text> : null}
    </Box>
  })
}
