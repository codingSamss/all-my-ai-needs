import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'
import type { Mood, Telemetry } from '../types'
import { pixelIconSvg, pixelMeterSvg, pixelPercentSvg } from './quota-pixels'
import { pixelLabelSvg, pixelQuotaCardSvg } from './quota-text'
import { DONE_SECONDS, SCENE_HEIGHT, SCENE_WIDTH, sceneSvg } from './scene'

// 本文件按显示需求独立实现；上游宠物素材仅在设备本地下载并校验。
const telemetry = atom({ plugin: 'pixel-buddy-sam', key: 'telemetry' } as const, {
  phase: 'idle', phaseAt: 0, clockAt: 0, cacheAt: null, context: null, limits: [],
} as Telemetry)
const animationAt = atom({ plugin: 'pixel-buddy-sam', key: 'animationAt' } as const, 0)
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

function themedScene(phase: Mood, elapsed: number): string {
  // 只去掉最外层底色；场景自己的天空、海面不变。散点颜色使用中性透明灰。
  return sceneSvg(phase, elapsed)
    .replace(/<rect x="-2" y="-2" width="104" height="22" fill="#[a-fA-F0-9]{6}"\/>/, '')
    .replace(/fill="#555"/g, 'fill="#919191" opacity="0.45"')
    .replace(/fill="#3c3c3c"/g, 'fill="#919191" opacity="0.24"')
    .replace(/fill="#2c2c2c"/g, 'fill="#919191" opacity="0.12"')
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
    await update($, telemetry, () => ({
      phase: 'idle', phaseAt: now, clockAt: now, cacheAt: null,
      context: usage.context, limits: usage.rateLimits,
    }))
    await update($, animationAt, () => now)
    $.clock.every(150, async () => {
      const tick = await $.clock.now()
      await update($, animationAt, () => tick)
    })
    $.clock.every(1000, async () => {
      const tick = await $.clock.now()
      const previous = await read($, telemetry)
      const warm = previous.cacheAt !== null && tick - previous.cacheAt < ttl + 2000
      if (warm || Math.floor(tick / 60000) !== Math.floor(previous.clockAt / 60000)) {
        await update($, telemetry, state => ({ ...state, clockAt: tick }))
      }
    })
    return next(event)
  })

  on('session.measure', async ($, event, next) => {
    const tick = await $.clock.now()
    await update($, telemetry, previous => ({
      ...previous, context: event.context,
      limits: event.rateLimits.length ? event.rateLimits : previous.limits,
      cacheAt: event.changed.includes('context') ? tick : previous.cacheAt,
      clockAt: tick,
    }))
    return next(event)
  })
  on('turn.start', async ($, event, next) => {
    const tick = await $.clock.now()
    await update($, telemetry, state => ({ ...state, phase: 'working', phaseAt: tick }))
    return next(event)
  })
  on('turn.complete', async ($, event, next) => {
    if (!event.agentId) {
      const tick = await $.clock.now()
      await update($, telemetry, state => ({ ...state,
        phase: event.isAborted || event.reason === 'error' ? 'idle' : 'done', phaseAt: tick,
      }))
    }
    return next(event)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, event, next) => {
    if (event.props.hasSurvey) return next(event)
    const { Box, Text } = $.ui.resolve(event)
    const state = await read($, telemetry)
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
    const tick = await read($, animationAt)
    const phase: Mood = event.props.isWorking ? 'working' : state.phase === 'working' ? 'idle' : state.phase
    const [shown, elapsed] = scenePhase(phase, Math.max(0, (tick - state.phaseAt) / 1000))
    return <Box flexDirection="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" columnGap={2} rowGap={1} paddingX={1}>
      <Box flexDirection="row" alignItems="center" flexWrap="wrap" columnGap={3} rowGap={1}>
        {items.map(item => {
          const card = pixelQuotaCardSvg(`${item.title}·剩余`, item.remaining, item.reset, item.color)
          return <Box key={item.kind} flexDirection="row" alignItems="center" flexShrink={0} gap={1}>
            <Svg source={pixelIconSvg(item.icon)} width={24} height={24} alt={`${item.title} quota window`} />
            {card ? <Svg source={card.source} width={card.width} height={card.height} alt={`${item.title} ${item.label} ${item.reset}`} />
              : <Box flexDirection="column" flexShrink={0} rowGap={1}>
                <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap={1}>
                  {label(`${item.title}·剩余`)}
                  <Svg source={pixelPercentSvg(item.remaining, item.color)} width={64} height={16} alt={item.label} />
                </Box>
                <Svg source={pixelMeterSvg(item.remaining, item.color)} width={140} height={10} alt={item.label} />
                {label(item.reset)}
              </Box>}
          </Box>
        })}
      </Box>
      <Svg source={themedScene(shown, elapsed)} width={SCENE_WIDTH} height={SCENE_HEIGHT}
        alt={`Claude is ${shown === 'done' ? 'celebrating' : shown === 'relax' ? 'relaxing' : shown}`} />
    </Box>
  })

  on('ui.render', { component: 'SessionMode' }, async ($, event, next) => {
    const { Box, Text } = $.ui.resolve(event)
    const state = await read($, telemetry)
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
