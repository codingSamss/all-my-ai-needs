import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, SessionCompactResult, SessionMessage } from 'claude-code'
import { DONE_SECONDS, FLASH_SECONDS, sceneSvg } from './hooks/scene'

const props = { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100, scroll: { offset: 0, bodyRows: 12 }, view: {} }
const now = Date.parse('2026-10-06T02:00:00Z')
const context = { window: 1_000_000, tokens: 175_000, percent: 17 }
const complete = (extra: Record<string, unknown> = {}) => ({ turnId: 'turn', answer: '', durationMs: 1000, isAborted: false, usage: null, ...extra })
const question = { question: 'Which one?', header: 'Pick', options: [{ label: 'A', description: 'a' }, { label: 'B', description: 'b' }], multiSelect: false }
const messages: SessionMessage[] = [{ role: 'user', text: 'fixture context', toolUses: [] }]
const unknownAlt = 'Claude task status is unknown'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(yes => { resolve = yes })
  return { promise, resolve }
}

// 测试自己的底层 hook 必须在首次调用 $ 之前注册，所以由 setup 在会话启动前接入。
async function fixture($: Engine, on: On, setup?: (clock: ReturnType<typeof mock.clock>) => void) {
  const clock = mock.clock(on, { now })
  on('session.usage', () => ({ value: { context, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.measure', (_, e) => ({ changed: e.changed }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('classic.Stop', () => ({}))
  setup?.(clock)
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [] })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const pet = async () => (await ui.findAll({ type: 'Svg' })).find(svg => String(svg.props.alt).startsWith('Claude'))
  const alt = async () => pet().then(svg => String(svg?.props.alt))
  return { clock, ui, pet, alt }
}

const step = { turnId: 'turn', index: 0, model: 'fixture-model', messageCount: 1 }
const stepResult = { turnId: 'turn', index: 0, answer: '', toolUses: [], stopReason: 'end_turn' as const, usage: null }

test('响应块种类决定思考、回复和干活；每一步开始先按干活，结束后清除', async ($, on) => {
  const { ui, alt } = await fixture($, on, () => on('turn.step', async function* () {
    yield { kind: 'thinking' as const, index: 0, text: 'hm' }
    yield { kind: 'thinking' as const, index: 0, text: 'mm' }
    yield { kind: 'text' as const, index: 1, text: 'hello' }
    yield { kind: 'text' as const, index: 1, text: ' world' }
    yield { kind: 'tool' as const, index: 2, id: 'call-1', name: 'Read' }
    yield { kind: 'input' as const, index: 2, json: '{}' }
    yield { kind: 'stop' as const, stopReason: 'tool_use' as const, usage: null }
    return stepResult
  }))
  await $.turn.start({ turnId: 'turn', text: '' })
  await ui.redraw({ ...props, isWorking: true })
  expect(await alt()).toBe('Claude is working')
  const seen: string[] = []
  for await (const chunk of $.turn.step(step)) seen.push(`${chunk.kind}:${await alt()}`)
  expect(seen).toEqual([
    'thinking:Claude is thinking', 'thinking:Claude is thinking', 'text:Claude is replying', 'text:Claude is replying',
    'tool:Claude is working', 'input:Claude is working', 'stop:Claude is working',
  ])
  // 下一步请求发出前先回到干活；回合结束后不能残留上一轮的回复画面。
  await $.turn.complete(complete())
  await ui.redraw({ ...props, isWorking: true })
  expect(await alt()).toBe('Claude is working')
  await ui.unmount()
})

test('回复块期间换到新一步，先回到干活再随块种类变化', async ($, on) => {
  const gate = deferred<void>()
  const { clock, ui, alt } = await fixture($, on, () => on('turn.step', async function* (_, e) {
    if (e.index === 0) yield { kind: 'text' as const, index: 0, text: 'first' }
    else {
      await gate.promise
      yield { kind: 'thinking' as const, index: 0, text: 'second' }
    }
    return { ...stepResult, index: e.index }
  }))
  await ui.redraw({ ...props, isWorking: true })
  for await (const chunk of $.turn.step(step)) expect(chunk.kind).toBe('text')
  expect(await alt()).toBe('Claude is replying')
  const seen: string[] = []
  const reading = (async () => { for await (const chunk of $.turn.step({ ...step, index: 1 })) seen.push(`${chunk.kind}:${await alt()}`) })()
  await clock.settle()
  // 第二步已发出请求但还没有任何块，不能停在上一步的回复画面。
  expect(await alt()).toBe('Claude is working')
  gate.resolve()
  await reading
  expect(seen).toEqual(['thinking:Claude is thinking'])
  await ui.unmount()
})

test('子代理的请求不改变主会话画面', async ($, on) => {
  const { ui, alt } = await fixture($, on, () => on('turn.step', async function* () {
    yield { kind: 'thinking' as const, index: 0, text: 'child' }
    return stepResult
  }))
  await $.turn.start({ turnId: 'turn', text: '' })
  await ui.redraw({ ...props, isWorking: true })
  for await (const chunk of $.turn.step({ ...step, agentId: 'child' })) {
    expect(chunk.kind).toBe('thinking')
    expect(await alt()).toBe('Claude is working')
  }
  await ui.unmount()
})

test('提问和计划确认期间显示等你，作答、拒绝、抛错后都恢复', async ($, on) => {
  let outcome = 'answer'
  const { clock, ui, alt } = await fixture($, on, clock => {
    on('tool.call', { tool: 'AskUserQuestion' }, async () => {
      await clock.sleep(1000)
      if (outcome === 'error') throw new Error('fixture failure')
      return outcome === 'deny' ? { deny: 'fixture refusal' } : { result: { questions: [], answers: {} } }
    })
    on('tool.call', { tool: 'ExitPlanMode' }, async () => {
      await clock.sleep(1000)
      return outcome === 'deny' ? { deny: 'fixture refusal' } : { result: { plan: 'fixture', isAgent: false } }
    })
  })
  await $.turn.start({ turnId: 'turn', text: '' })
  await ui.redraw({ ...props, isWorking: true })
  for (const tool of ['AskUserQuestion', 'ExitPlanMode'] as const) {
    for (outcome of ['answer', 'deny', 'error']) {
      if (tool === 'ExitPlanMode' && outcome === 'error') continue
      const call = tool === 'AskUserQuestion'
        ? $.tool.call({ tool, tool_use_id: `${tool}-${outcome}`, questions: [question] })
        : $.tool.call({ tool, tool_use_id: `${tool}-${outcome}` })
      const pending = call.catch(() => {})
      await clock.settle()
      expect(await alt()).toBe('Claude is waiting for your answer')
      await clock.advance(1000)
      await pending
      expect(await alt()).toBe('Claude is working')
    }
  }
  await ui.unmount()
})

test('两个提问交错结束时，先答完的不会撤掉仍在等的画面；压缩优先于等你', async ($, on) => {
  const compact = deferred<SessionCompactResult>()
  const { clock, ui, alt } = await fixture($, on, clock => {
    on('tool.call', { tool: 'AskUserQuestion' }, async (_, e) => {
      await clock.sleep(e.tool_use_id === 'slow' ? 2000 : 1000)
      return { result: { questions: [], answers: {} } }
    })
    on('session.compact', () => compact.promise)
  })
  await ui.redraw({ ...props, isWorking: true })
  const calls = ['fast', 'slow'].map(id => $.tool.call({ tool: 'AskUserQuestion', tool_use_id: id, questions: [question] }))
  await clock.settle()
  expect(await alt()).toBe('Claude is waiting for your answer')
  await clock.advance(1000)
  await calls[0]
  expect(await alt()).toBe('Claude is waiting for your answer')
  const compacting = $.session.compact({ trigger: 'manual', messages })
  await clock.settle()
  expect(await alt()).toBe('Claude is compacting')
  compact.resolve({ messages })
  await compacting
  expect(await alt()).toBe('Claude is waiting for your answer')
  await clock.advance(1000)
  await calls[1]
  expect(await alt()).toBe('Claude is working')
  await ui.unmount()
})

for (const [label, extra, expected] of [
  ['出错', { reason: 'error' }, 'Claude hit an error'],
  ['拒答', { reason: 'refusal', refusal: { category: null, explanation: null } }, 'Claude hit an error'],
  ['中断', { isAborted: true, reason: 'aborted' }, 'Claude was interrupted'],
] as const) {
  test(`${label}只闪现一小会儿，随后回到未知；新一轮立即覆盖`, async ($, on) => {
    const { clock, ui, alt } = await fixture($, on)
    await $.turn.start({ turnId: 'turn', text: '' })
    await ui.redraw({ ...props, isWorking: true })
    // 子代理自己的失败不属于主会话。
    await $.turn.complete(complete({ ...extra, agentId: 'child' }))
    expect(await alt()).toBe('Claude is working')
    await $.turn.complete(complete(extra))
    await ui.redraw(props)
    expect(await alt()).toBe(expected)
    const flash = String((await ui.findAll({ type: 'Svg' })).find(svg => svg.props.alt === expected)?.props.source)
    expect(flash).toContain('<animate')
    await clock.advance((FLASH_SECONDS - 1) * 1000)
    expect(await alt()).toBe(expected)
    await clock.advance(1000)
    expect(await alt()).toBe(unknownAlt)
    await $.turn.start({ turnId: 'next', text: '' })
    await ui.redraw({ ...props, isWorking: true })
    expect(await alt()).toBe('Claude is working')
    await clock.advance(FLASH_SECONDS * 1000)
    expect(await alt()).toBe('Claude is working')
    await ui.unmount()
  })
}

test('出错后若仍有后台任务，等待画面优先于出错画面', async ($, on) => {
  const { ui, alt } = await fixture($, on)
  await $.turn.start({ turnId: 'turn', text: '' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [{ id: 'live-shell', type: 'shell', status: 'running', description: 'fixture' }] })
  await $.turn.complete(complete({ reason: 'error' }))
  expect(await alt()).toBe('Claude is waiting for scripts or subagents')
  await ui.unmount()
})

for (const [minutes, stage] of [[1, 'hot'], [31, 'warm'], [61, 'cold']] as const) {
  test(`缓存剩余寿命决定咖啡温度：${stage}`, async ($, on) => {
    const { clock, ui, pet, alt } = await fixture($, on)
    await $.session.measure({ context, rateLimits: [], changed: ['context'] })
    await clock.advance(minutes * 60000)
    await $.turn.complete(complete())
    expect(await alt()).toBe('Claude is celebrating')
    await clock.advance(DONE_SECONDS * 1000)
    expect(await alt()).toBe('Claude is relaxing')
    expect((await pet())?.props.source).toBe(sceneSvg('relax', stage))
    await ui.unmount()
  })
}

test('咖啡温度只在跨过半寿命和过期时换画面，其余秒级计时不重绘', async ($, on) => {
  const { clock, ui, pet } = await fixture($, on)
  await $.session.measure({ context, rateLimits: [], changed: ['context'] })
  await $.turn.complete(complete())
  await clock.advance(DONE_SECONDS * 1000)
  const sources = new Set<string>()
  // 每 30 秒重新完成一轮并观察休息画面，覆盖一小时多一点：热 -> 温 -> 凉，各一个来源。
  for (let i = 0; i < 125; i++) {
    await $.turn.complete(complete())
    await clock.advance(DONE_SECONDS * 1000)
    sources.add(String((await pet())?.props.source))
    await clock.advance(30000 - DONE_SECONDS * 1000)
  }
  expect([...sources]).toEqual([sceneSvg('relax', 'hot'), sceneSvg('relax', 'warm'), sceneSvg('relax', 'cold')])
  await ui.unmount()
})

test('固定房间只在睡觉时转为夜晚，咖啡温度只影响休息画面', () => {
  const night = 'fill="var(--v-night)"'
  for (const mood of ['working', 'thinking', 'replying', 'asking', 'waiting', 'compact', 'unknown', 'done', 'relax', 'error', 'aborted'] as const) {
    expect(sceneSvg(mood)).not.toContain(night)
    if (mood !== 'relax') for (const cache of ['warm', 'cold'] as const) expect(sceneSvg(mood, cache)).toBe(sceneSvg(mood))
  }
  expect(sceneSvg('idle')).toContain(night)
  expect(sceneSvg('relax', 'hot')).not.toBe(sceneSvg('relax', 'warm'))
  expect(sceneSvg('relax', 'warm')).not.toBe(sceneSvg('relax', 'cold'))
  // 房间是固定摆设：舞台之前没有任何动画，未知状态整幅画面静止。
  for (const mood of ['working', 'idle', 'relax', 'unknown'] as const) {
    const svg = sceneSvg(mood)
    expect(svg.slice(0, svg.indexOf('<defs>'))).not.toContain('<animate')
  }
  expect(sceneSvg('unknown')).not.toContain('<animate')
})

test('小人只有两只眼睛：静止画面里眼睛色块恰好两个，没有嘴和额外的手', () => {
  const eye = (svg: string) => svg.split('fill="#2b1b17"').length - 1
  // 未知与睡觉各自只有一对眼睛；没有第三块同色像素，也就没有嘴。
  expect(eye(sceneSvg('unknown'))).toBe(2)
  expect(eye(sceneSvg('idle'))).toBe(2)
  for (const mood of ['idle', 'working', 'thinking', 'replying', 'asking', 'waiting', 'compact', 'unknown', 'done', 'relax', 'error', 'aborted'] as const) {
    expect(sceneSvg(mood)).not.toContain('<ellipse')
    expect(sceneSvg(mood)).not.toContain('<circle')
  }
})
