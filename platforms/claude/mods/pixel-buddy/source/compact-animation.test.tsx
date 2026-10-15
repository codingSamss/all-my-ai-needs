import { expect, mock, test } from 'claude-code/testing'
import type { SessionCompactResult, SessionMessage } from 'claude-code'

const now = Date.parse('2026-10-15T03:00:00Z')
const props = { hasSurvey: false, isWorking: true, maxRows: 12, bodyColumns: 100,
  scroll: { offset: 0, bodyRows: 12 }, view: {} }
const mount = { plugin: 'pixel-buddy-sam', surface: 'desktop' as const, component: 'AbovePrompt' as const, props }
const context = { tokens: 400000, window: 1000000, percent: 40 }
const messages: SessionMessage[] = [{ role: 'user', text: 'fixture context', toolUses: [] }]

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

for (const trigger of ['auto', 'manual', 'plugin'] as const) {
  test(`${trigger} 真实压缩期间覆盖工作画面，结束恢复并刷新统计`, async ($, on) => {
    mock.clock(on, { now })
    const started = deferred<void>(), result = deferred<SessionCompactResult>()
    let tokens = 400000, calls = 0, reads = 0
    on('session.usage', () => {
      reads++
      return { value: { context: { ...context, breakdown: { totalTokens: tokens,
        autoCompactThreshold: 400000, isAutoCompactEnabled: true } }, rateLimits: [] } }
    })
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    on('session.compact', (_, e) => {
      calls++
      expect(e.trigger).toBe(trigger)
      expect(e.instructions).toBe('keep the plan')
      started.resolve()
      return result.promise
    })
    await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
    const ui = await $.ui.mount(mount)
    const footer = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
    // 达到 100% 只有进度提示；真实事件尚未开始时不播放压缩。
    expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is working')
    const pending = $.session.compact({ trigger, messages, instructions: 'keep the plan' })
    await started.promise
    const press = (await ui.findAll({ type: 'Svg' })).find(s => s.props.alt === 'Claude is compacting')
    expect(press?.props.height).toBe(54)
    expect(String(press?.props.source)).toContain('var(--pb-press,')
    tokens = 120000
    const answer = { messages, tokensBefore: 400000, tokensAfter: tokens }
    result.resolve(answer)
    expect(await pending).toEqual(answer)
    expect(calls).toBe(1)
    expect(reads).toBe(2)
    expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is working')
    expect((await footer.findAll({ type: 'Text' })).some(n => n.text === '30%' && n.props.color === '#4cc35a')).toBe(true)
    expect(await footer.find({ text: '120k/400k' })).toBeDefined()
    await footer.unmount()
    await ui.unmount()
  })
}

for (const extra of [{ trigger: 'precompute' as const }, { trigger: 'auto' as const, agentId: 'helper' }]) {
  test(`${extra.agentId ?? extra.trigger} 不冒充主会话正在压缩`, async ($, on) => {
    mock.clock(on, { now })
    const started = deferred<void>(), result = deferred<SessionCompactResult>()
    let reads = 0
    on('session.usage', () => { reads++; return { value: { context, rateLimits: [] } } })
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    on('session.compact', () => { started.resolve(); return result.promise })
    await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
    const ui = await $.ui.mount(mount)
    const before = await ui.drawn()
    const pending = $.session.compact({ ...extra, messages })
    await started.promise
    expect(await ui.drawn()).toEqual(before)
    result.resolve({ messages })
    await pending
    expect(await ui.drawn()).toEqual(before)
    expect(reads).toBe(1)
    await ui.unmount()
  })
}

for (const fail of [false, true]) {
  test(`压缩${fail ? '抛错' : '被跳过'}时退出动画并保留原结果`, async ($, on) => {
    mock.clock(on, { now })
    const started = deferred<void>(), result = deferred<SessionCompactResult>()
    let calls = 0
    on('session.usage', () => ({ value: { context, rateLimits: [] } }))
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    on('session.compact', () => { calls++; started.resolve(); return result.promise })
    await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
    const ui = await $.ui.mount(mount)
    // 立即接住拒绝，避免测试环境把等待 UI 检查期间的失败当作未处理异常。
    const pending = $.session.compact({ trigger: 'auto', messages }).then(value => ({ value }), error => ({ error }))
    await started.promise
    expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is compacting')
    if (fail) result.reject(new Error('fixture compact failure'))
    else result.resolve({ skip: 'fixture blocked' })
    const settled = await pending
    // 测试宿主会把底层异常包装为 HooksError；要求失败继续向上传递，不能被 UI 清理吞掉。
    if (fail) expect(String('error' in settled ? settled.error : '')).toContain('HooksError: no implementation for session.compact')
    else expect(settled).toEqual({ value: { skip: 'fixture blocked' } })
    expect(calls).toBe(1)
    expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is working')
    await ui.unmount()
  })
}

test('两个压缩请求交错结束时，先完成的请求不会撤掉仍在运行的动画', async ($, on) => {
  mock.clock(on, { now })
  const started = [deferred<void>(), deferred<void>()], results = [deferred<SessionCompactResult>(), deferred<SessionCompactResult>()]
  let calls = 0
  on('session.usage', () => ({ value: { context, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.compact', () => { const index = calls++; started[index].resolve(); return results[index].promise })
  on('turn.complete', () => ({ text: '' }))
  on('classic.Stop', () => ({}))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [] })
  const ui = await $.ui.mount(mount)
  const first = $.session.compact({ trigger: 'auto', messages })
  await started[0].promise
  const second = $.session.compact({ trigger: 'manual', messages })
  await started[1].promise
  results[0].resolve({ messages })
  await first
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is compacting')
  await $.turn.complete({ turnId: 'one', answer: '', durationMs: 1000, isAborted: false, usage: null })
  await ui.redraw({ ...props, isWorking: false })
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is compacting')
  results[1].resolve({ messages })
  await second
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is celebrating')
  await ui.unmount()
})

for (const isWorking of [false, true]) test(`后台任务仍在运行时压缩优先，结束恢复${isWorking ? '主会话工作' : '后台等待'}`, async ($, on) => {
  mock.clock(on, { now })
  const started = deferred<void>(), result = deferred<SessionCompactResult>()
  let tokens = 400000
  on('session.usage', () => ({ value: { context: { ...context, breakdown: {
    totalTokens: tokens, autoCompactThreshold: 400000, isAutoCompactEnabled: true,
  } }, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('classic.Stop', () => ({}))
  on('prompt.submit', (_, e) => ({ text: e.text, origin: e.origin }))
  on('session.compact', () => { started.resolve(); return result.promise })
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [{ id: 'shell-bg', type: 'shell', status: 'running', description: 'fixture' }] })
  const ui = await $.ui.mount({ ...mount, props: { ...props, isWorking } })
  const footer = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
  const alt = async () => (await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)
  const restored = isWorking ? 'Claude is working' : 'Claude is waiting for scripts or subagents'
  expect(await alt()).toContain(restored)
  const pending = $.session.compact({ trigger: 'auto', messages })
  await started.promise
  expect(await alt()).toContain('Claude is compacting')
  tokens = 120000
  result.resolve({ messages, tokensBefore: 400000, tokensAfter: tokens })
  await pending
  expect(await alt()).toContain(restored)
  expect(await footer.find({ text: '120k/400k' })).toBeDefined()
  await $.prompt.submit({ text: '<task-notification><task-id>shell-bg</task-id><status>completed</status></task-notification>', wait: false, origin: { kind: 'task-notification' } })
  expect(await alt()).toContain(isWorking ? 'Claude is working' : 'Claude is relaxing')
  expect(await alt()).not.toContain('Claude is celebrating')
  await footer.unmount()
  await ui.unmount()
})

test('旧会话压缩结束不能撤掉新会话压缩或额外刷新读数', async ($, on) => {
  mock.clock(on, { now })
  const started = [deferred<void>(), deferred<void>()], results = [deferred<SessionCompactResult>(), deferred<SessionCompactResult>()]
  let calls = 0, reads = 0
  on('session.usage', () => { reads++; return { value: { context, rateLimits: [] } } })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.compact', () => { const index = calls++; started[index].resolve(); return results[index].promise })
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount(mount)
  const old = $.session.compact({ trigger: 'auto', messages })
  await started[0].promise
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const current = $.session.compact({ trigger: 'manual', messages })
  await started[1].promise
  results[0].resolve({ messages })
  await old
  expect(reads).toBe(2)
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is compacting')
  results[1].resolve({ messages })
  await current
  expect(reads).toBe(3)
  expect((await ui.findAll({ type: 'Svg' })).map(s => s.props.alt)).toContain('Claude is working')
  await ui.unmount()
})
