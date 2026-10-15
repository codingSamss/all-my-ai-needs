import { expect, mock, test } from 'claude-code/testing'
import { pixelLabelSvg } from './hooks/quota-text'
import { DONE_SECONDS, sceneSvg } from './hooks/scene'

  test('旧宿主缺少压缩阈值时，底栏用短提示而不伪造进度', async ($, on) => {
    mock.clock(on, { now: Date.parse('2026-10-06T02:00:00Z') })
    on('session.usage', () => ({ value: { context: { percent: 52, tokens: 516000, window: 1000000 }, rateLimits: [] } }))
    on('session.start', (_, event) => ({ cwd: event.cwd }))
    await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
    const mounted = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
    const texts = await mounted.findAll({ type: 'Text' })
    const percentage = texts.find(item => item.text === '待更新')
    expect(percentage?.props.dimColor).toBe(true)
    expect(texts.some(item => item.text?.includes('▰'))).toBe(false)
    await mounted.unmount()
  })

test('宠物外层底色透明，保留场景画布', async ($, on) => {
  mock.clock(on, { now: Date.parse('2026-10-06T02:00:00Z') })
  on('session.usage', () => ({ value: { context: { window: 1000000 }, rateLimits: [] } }))
  on('session.start', (_, event) => ({ cwd: event.cwd }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const mounted = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props: {
    hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100,
    scroll: { offset: 0, bodyRows: 12 }, view: {},
  } })
  const pet = (await mounted.findAll({ type: 'Svg' })).find(item => item.props.alt === 'Claude task status is unknown')
  expect(String(pet?.props.source).includes('x="-2" y="-2" width="104" height="22"')).toBe(false)
  expect(String(pet?.props.source).includes('viewBox="0 0 256 27"')).toBe(true)
  await mounted.unmount()
})

const props = {
  hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100,
  scroll: { offset: 0, bodyRows: 12 }, view: {},
}
const now = Date.parse('2026-10-06T02:00:00Z')
const context = { window: 1_000_000, tokens: 175_000, percent: 17 }

test('宿主用量转成剩余像素读数，倒计时推进不额外读取用量', async ($, on) => {
  const clock = mock.clock(on, { now })
  let reads = 0
  on('session.usage', () => {
    reads++
    return { value: { context, rateLimits: [
      { kind: 'five_hour', percentUsed: 15, resetsAt: new Date(now + 285 * 60_000).toISOString() },
      { kind: 'seven_day', percentUsed: 44, resetsAt: new Date(now + 139 * 60 * 60_000).toISOString() },
    ] } }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const svgs = await ui.findAll({ type: 'Svg' })
  expect(svgs).toHaveLength(5)
  expect(svgs.map(s => s.props.alt)).toContain('5h 剩余85% 4小时45分后重置')
  expect(svgs.map(s => s.props.alt)).toContain('7d 剩余56% 5天19小时后重置')
  expect(svgs.map(s => s.props.alt)).toContain('Claude task status is unknown')
  for (const card of svgs.filter(s => String(s.props.alt).includes('剩余'))) {
    expect(card.props.width).toBe(112)
    expect(card.props.height).toBe(52)
  }
  await clock.advance(60_000)
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('5h 剩余85% 4小时44分后重置')
  expect(reads).toBe(1)
  await ui.unmount()
})

test('缺少用量保持未知，零剩余保持零；底栏与终端文字可用', async ($, on) => {
  mock.clock(on, { now })
  on('session.usage', () => ({ value: { context, rateLimits: [{ kind: 'five_hour', percentUsed: 100 }] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const svgs = await ui.findAll({ type: 'Svg' })
  expect(svgs.map(s => s.props.alt)).toContain('5h 剩余0% 重置时间待更新')
  expect(svgs.map(s => s.props.alt)).toContain('7d 剩余 — 重置时间待更新')
  for (const card of svgs.filter(s => String(s.props.alt).includes('剩余'))) {
    const meter = String(card.props.source).match(/<g transform="translate\(0 22\)">([\s\S]*?)<\/g>/)?.[1] ?? ''
    expect((meter.match(/<rect /g) ?? []).length).toBe(10)
  }
  const terminal = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'terminal', component: 'AbovePrompt', props })
  expect((await terminal.find({ type: 'Text' }))?.text).toBe('5h 剩余0%   7d 剩余 —')
  const footer = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
  expect(await footer.find({ text: '待更新' })).toBeDefined()
  await footer.unmount()
  await terminal.unmount()
  await ui.unmount()
})

test('首轮响应前中断保持等待，收到摘要后显示进度与零用量', async ($, on) => {
  mock.clock(on, { now })
  let snapshot = { context: { window: 1000000 } } as { context: { window: number; tokens?: number; percent?: number; breakdown?: { totalTokens: number; autoCompactThreshold: number; isAutoCompactEnabled: boolean } } }
  on('session.usage', () => ({ value: { ...snapshot, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.complete', () => ({ text: '' }))
  on('session.measure', (_, e) => ({ changed: e.changed }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: ['focus'] } })
  await $.turn.complete({ turnId: 'interrupted', answer: '', durationMs: 1000, isAborted: true, usage: null })
  expect(await ui.find({ text: 'cache / ctx 待首轮响应 · focus' })).toBeDefined()
  for (const tokens of [175000, 0]) {
    snapshot = { context: { ...context, tokens, breakdown: { totalTokens: tokens, autoCompactThreshold: 400000, isAutoCompactEnabled: true } } }
    await $.session.measure({ context: snapshot.context, rateLimits: [], changed: ['context'] })
    expect(await ui.find({ text: 'cache 60:00' })).toBeDefined()
    expect(await ui.find({ text: tokens ? '175k/400k' : '0/400k' })).toBeDefined()
    expect(await ui.find({ text: 'focus' })).toBeDefined()
    expect((await ui.findAll({ type: 'Text' })).some(n => n.text?.includes('压缩') || n.text?.includes('▰'))).toBe(false)
  }
  await ui.unmount()
})

test('已有上下文的重载不伪造缓存时间，原生提示槽保持透传', async ($, on) => {
  mock.clock(on, { now })
  on('session.usage', () => ({ value: { context, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.render', { component: 'PromptHint' }, () => ({ type: 'Text', props: {}, children: ['native hint'] }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const footer = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
  expect(await footer.find({ text: 'cache 待更新' })).toBeDefined()
  expect(await footer.find({ text: '待更新' })).toBeDefined()
  const hint = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'PromptHint', props: {
    isDraft: false, isWorking: false, hint: 'native hint',
  } })
  expect((await hint.findAll({ type: 'Text' })).map(t => t.text)).toEqual(['native hint'])
  await hint.unmount()
  await footer.unmount()
})

test('问卷占位时仍将渲染交回宿主', async ($, on) => {
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Text', props: {}, children: ['Survey fixture'] }))
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props: { ...props, hasSurvey: true } })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('Survey fixture')
  await ui.unmount()
})

test('中文标签保留原义，未知字和超宽内容回退普通文字', () => {
  for (const text of ['5h·剩余', '7d·剩余', '4小时59分后重置', '6天23小时后重置', '重置时间待更新']) {
    const label = pixelLabelSvg(text)
    expect(label).toBeDefined()
    expect(label?.width).toBeLessThanOrEqual(140)
    expect(label?.height).toBe(12)
  }
  expect(pixelLabelSvg('不在字库的字')).toBeUndefined()
  expect(pixelLabelSvg('天'.repeat(20))).toBeUndefined()
  expect(pixelLabelSvg('<script>')).toBeUndefined()
})

test('cache 秒级倒计时和重复用量事件不替换宠物 SVG', async ($, on) => {
  const clock = mock.clock(on, { now })
  const limits = [{ kind: 'five_hour', percentUsed: 15 }]
  on('session.usage', () => ({ value: { context, rateLimits: limits } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.measure', (_, e) => ({ changed: e.changed }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  await $.session.measure({ context, rateLimits: limits, changed: ['context'] })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const footer = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
  const original = await ui.drawn()
  const pet = (await ui.findAll({ type: 'Svg' })).find(s => s.props.alt === 'Claude task status is unknown')
  expect(pet?.props.isInteractive).toBe(true)
  expect(String(pet?.props.source)).toContain('<animate')
  for (let i = 0; i < 20; i++) {
    await clock.advance(1000)
    await $.session.measure({ context, rateLimits: limits, changed: ['rateLimits'] })
    expect(await ui.drawn()).toEqual(original)
  }
  expect(await footer.find({ text: 'cache 59:40' })).toBeDefined()
  await footer.unmount()
  await ui.unmount()
})

test('模拟一小时保持同一动画源，额度读取不轮询', async ($, on) => {
  const clock = mock.clock(on, { now })
  let reads = 0
  on('session.usage', () => { reads++; return { value: { context, rateLimits: [] } } })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const sources = new Set<string>()
  // 每 1.5 秒观察一次，既覆盖旧 150 ms 刷新，也覆盖新的分钟边界。
  for (let i = 0; i <= 2400; i++) {
    const pet = (await ui.findAll({ type: 'Svg' })).find(s => s.props.alt === 'Claude task status is unknown')
    sources.add(String(pet?.props.source))
    if (i < 2400) await clock.advance(1500)
  }
  expect(sources.size).toBe(1)
  expect(reads).toBe(1)
  await ui.unmount()
})

test('庆祝切换到休息和空闲，旧回调不能打断新任务', async ($, on) => {
  const clock = mock.clock(on, { now })
  on('session.usage', () => ({ value: { context, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('classic.Stop', () => ({}))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [] })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  await $.turn.complete({ turnId: 'one', answer: '', durationMs: 1000, isAborted: false, usage: null })
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is celebrating')
  await clock.advance(DONE_SECONDS * 1000)
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is relaxing')
  await clock.advance(240000)
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is idle')
  await $.turn.complete({ turnId: 'two', answer: '', durationMs: 1000, isAborted: false, usage: null })
  await clock.advance(1000)
  await $.turn.start({ turnId: 'three', text: '' })
  await ui.redraw({ ...props, isWorking: true })
  const working = await ui.drawn()
  await clock.advance(DONE_SECONDS * 1000)
  expect(await ui.drawn()).toEqual(working)
  await ui.unmount()
})

test('各状态使用稳定的浏览器动画源，不引入执行结果文案', () => {
  for (const mood of ['idle', 'working', 'done', 'relax', 'compact', 'waiting', 'unknown'] as const) {
    const svg = sceneSvg(mood)
    expect(svg).toContain('<animate')
    expect(svg).not.toContain('{{')
    expect(sceneSvg(mood)).toBe(svg)
    expect(svg).not.toContain('undefined')
    expect(svg).not.toContain('NaN')
    expect(svg).not.toContain('<script')
    expect(svg.length).toBeLessThan(131072)
  }
})


test('子任务完成、异常和中断不播放主任务庆祝', async ($, on) => {
  mock.clock(on, { now })
  on('session.usage', () => ({ value: { context, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.complete', () => ({ text: '' }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  for (const extra of [{ agentId: 'child' }, { isAborted: true }, { reason: 'error' as const }]) {
    await $.turn.complete({ turnId: 'one', answer: '', durationMs: 1000, isAborted: false, usage: null, ...extra })
    expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).not.toContain('Claude is celebrating')
  }
  await ui.unmount()
})

test('窄宽窗口均保持单行，动画由可收缩容器裁边', async ($, on) => {
  mock.clock(on, { now })
  on('session.usage', () => ({ value: { context, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  for (const bodyColumns of [45, 95, 160]) {
    await ui.redraw({ ...props, bodyColumns })
    const boxes = await ui.findAll({ type: 'Box' })
    expect(boxes.some(b => b.props.flexWrap === 'wrap')).toBe(false)
    expect(boxes.some(b => b.props.flexGrow === 1 && b.props.minWidth === 0 && b.props.overflow === 'hidden')).toBe(true)
    const pet = (await ui.findAll({ type: 'Svg' })).find(s => s.props.alt === 'Claude task status is unknown')
    expect(pet?.props.height).toBe(54)
  }
  await ui.unmount()
})
