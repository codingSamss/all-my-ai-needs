import { expect, mock, test } from 'claude-code/testing'
import { compactionState, contextProgress } from './hooks/context-progress'

const now = Date.parse('2026-10-15T02:00:00Z')
const footerMount = { plugin: 'pixel-buddy-sam', surface: 'desktop' as const, component: 'SessionMode' as const, props: { modes: [] } }

function usage(tokens = 362000, threshold = 400000, enabled = true) {
  return { context: { tokens: Math.max(0, tokens - 1234), window: 1000000, percent: Math.round(tokens / 10000), breakdown: {
    categories: [], totalTokens: tokens, maxTokens: 450000, rawMaxTokens: 450000,
    autocompactSource: 'settings' as const, percentage: 81, gridRows: [], model: 'fixture-model',
    memoryFiles: [], mcpTools: [], agents: [], apiUsage: null,
    isAutoCompactEnabled: enabled, autoCompactThreshold: enabled ? threshold : undefined,
  } }, rateLimits: [] }
}

for (const [tokens, label, color] of [[208000, '压缩52%', '#4cc35a'], [280000, '压缩70%', '#e5a33a'], [362000, '压缩90.5%', '#e5534b']] as const) {
  test(`实际触发阈值决定 ${label} 与颜色，不使用模型容量或窗口容量`, async ($, on) => {
    mock.clock(on, { now })
    on('session.usage', (_, event) => {
      expect(event.breakdown).toBe('summary')
      return { value: usage(tokens) }
    })
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
    const ui = await $.ui.mount(footerMount)
    const labels = await ui.findAll({ type: 'Text' })
    expect(contextProgress(usage(tokens).context, compactionState(usage(tokens).context.breakdown)).label).toBe(label)
    expect(labels.find(item => item.text === `${Math.floor(tokens / 400000 * 100)}%` && item.props.color === color)).toBeDefined()
    expect(labels.some(item => item.text?.includes('压缩') || item.text?.includes('▰'))).toBe(false)
    expect(await ui.find({ text: `${tokens / 1000}k/400k` })).toBeDefined()
    expect(await ui.findAll({ type: 'Svg' })).toHaveLength(0)
    await ui.unmount()
  })
}

test('自动压缩关闭、字段缺失和非法阈值均不伪造进度', () => {
  const context = usage().context
  expect(contextProgress(context, compactionState({ isAutoCompactEnabled: false, autoCompactThreshold: 400000 })).detail).toContain('自动压缩已关')
  for (const threshold of [undefined, 0, -1, NaN, Infinity]) {
    const progress = contextProgress(context, compactionState({ isAutoCompactEnabled: true, autoCompactThreshold: threshold }))
    expect(progress.label).toBe('ctx36%')
    expect(progress.detail).toContain('压缩阈值未知')
    expect(progress.percent).toBe(null)
    expect(progress.ratio).toBe(null)
  }
  expect(contextProgress(context, compactionState()).detail).toContain('压缩阈值未知')
})

test('零用量、未知用量、临近阈值与超额不会混淆', () => {
  const state = (totalTokens?: number) => compactionState({ isAutoCompactEnabled: true, autoCompactThreshold: 400000, totalTokens })
  expect(contextProgress(null, state(0)).label).toBe('压缩0%')
  expect(contextProgress(null, state(0)).ratio).toBe('0/400k')
  for (const tokens of [undefined, NaN, -1, Infinity]) {
    const progress = contextProgress({ tokens: 362000, window: 1000000 }, state(tokens))
    expect(progress.label).toBe('压缩 —')
    expect(progress.detail).toContain('用量待更新')
    expect(progress.ratio).toBe(null)
  }
  const near = contextProgress(null, state(399999))
  expect(near.label).toBe('压缩99.9%')
  for (const tokens of [400000, 440000]) {
    expect(contextProgress(null, state(tokens)).detail).toContain('已达压缩线')
  }
})

test('上下文变化刷新阈值，秒级计时和账号额度变化不轮询明细', async ($, on) => {
  const clock = mock.clock(on, { now })
  let snapshot = usage(175000)
  let reads = 0
  on('session.usage', () => { reads++; return { value: snapshot } })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.measure', (_, e) => ({ changed: e.changed }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount(footerMount)
  snapshot = usage(180000, 200000)
  await $.session.measure({ context: snapshot.context, rateLimits: [], changed: ['context'] })
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text === '90%' && n.props.color === '#e5534b')).toBe(true)
  expect(await ui.find({ text: '180k/200k' })).toBeDefined()
  for (let i = 0; i < 20; i++) {
    await clock.advance(1000)
    await $.session.measure({ context: snapshot.context, rateLimits: [], changed: ['rateLimits'] })
  }
  expect(reads).toBe(2)
  expect(await ui.find({ text: 'cache 59:40' })).toBeDefined()
  await ui.unmount()
})

test('读取失败后清除旧阈值，不把旧配置继续显示成真实进度', async ($, on) => {
  mock.clock(on, { now })
  let fail = false
  on('session.usage', () => {
    if (fail) throw new Error('fixture read failure')
    return { value: usage() }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.measure', (_, e) => ({ changed: e.changed }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount(footerMount)
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text === '90%' && n.props.color === '#e5534b')).toBe(true)
  fail = true
  await $.session.measure({ context: usage().context, rateLimits: [], changed: ['context'] })
  expect(await ui.find({ text: '待更新' })).toBeDefined()
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text?.includes('▰'))).toBe(false)
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text?.includes('/400k'))).toBe(false)
  await ui.unmount()
})

test('修改压缩窗口的命令先交回宿主，随后读取生效值', async ($, on) => {
  mock.clock(on, { now })
  let snapshot = usage(175000)
  let commands = 0
  on('session.usage', () => ({ value: snapshot }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('command.run', { command: 'autocompact' }, (_, e) => {
    commands++
    expect(e.args).toBe('200k')
    snapshot = usage(175000, 200000)
    return { text: 'fixture updated' }
  })
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount(footerMount)
  expect(await $.command.run({ command: 'autocompact', args: '200k' })).toEqual({ text: 'fixture updated' })
  expect(commands).toBe(1)
  expect(await ui.find({ text: '175k/200k' })).toBeDefined()
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text === '87%' && n.props.color === '#e5a33a')).toBe(true)
  await ui.unmount()
})

test('较早的明细请求不能覆盖命令修改后的新阈值', async ($, on) => {
  mock.clock(on, { now })
  let reads = 0
  let releaseOld!: (value: { value: ReturnType<typeof usage> }) => void
  let reportStarted!: () => void
  const started = new Promise<void>(resolve => { reportStarted = resolve })
  const old = new Promise<{ value: ReturnType<typeof usage> }>(resolve => { releaseOld = resolve })
  on('session.usage', () => {
    reads++
    if (reads === 2) { reportStarted(); return old }
    return { value: usage(175000, reads > 2 ? 200000 : 400000) }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.measure', (_, e) => ({ changed: e.changed }))
  on('command.run', { command: 'autocompact' }, () => ({ text: 'fixture updated' }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount(footerMount)
  const pending = $.session.measure({ context: usage(175000).context, rateLimits: [], changed: ['context'] })
  await started
  await $.command.run({ command: 'autocompact', args: '200k' })
  releaseOld({ value: usage(175000, 400000) })
  await pending
  expect(await ui.find({ text: '175k/200k' })).toBeDefined()
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text === '87%' && n.props.color === '#e5a33a')).toBe(true)
  await ui.unmount()
})

test('关闭自动压缩保留宿主结果，刷新后明确显示已关', async ($, on) => {
  mock.clock(on, { now })
  let enabled = true
  on('session.usage', () => ({ value: usage(175000, 400000, enabled) }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('config.set', { key: 'autoCompact' }, (_, e) => {
    enabled = e.value === true
    return { value: e.value }
  })
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount(footerMount)
  expect(await $.config.set({ key: 'autoCompact', value: false })).toEqual({ value: false })
  expect(await ui.find({ text: '已关闭' })).toBeDefined()
  expect((await ui.findAll({ type: 'Text' })).some(n => n.text?.includes('/400k'))).toBe(false)
  await ui.unmount()
})
