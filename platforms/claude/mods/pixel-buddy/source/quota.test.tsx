import { expect, mock, test } from 'claude-code/testing'
import { pixelLabelSvg } from './hooks/quota-text'

for (const [percent, color] of [[52, '#4cc35a'], [70, '#e5a33a'], [90, '#e5534b']] as const) {
  test(`ctx ${percent}% 按阈值高亮，token 数量保持弱色`, async ($, on) => {
    mock.clock(on, { now: Date.parse('2026-10-06T02:00:00Z') })
    on('session.usage', () => ({ value: { context: { percent, tokens: 516000, window: 1000000 }, rateLimits: [] } }))
    on('session.start', (_, event) => ({ cwd: event.cwd }))
    await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
    const mounted = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'SessionMode', props: { modes: [] } })
    const texts = await mounted.findAll({ type: 'Text' })
    const percentage = texts.find(item => item.text === `ctx${percent}%`)
    expect(percentage?.props.color).toBe(color)
    const tokens = texts.find(item => item.text === ' 516k/1M')
    expect(tokens?.props.dimColor).toBe(true)
    await mounted.unmount()
  })
}

test('宠物外层底色透明，保留场景画布', async ($, on) => {
  mock.clock(on, { now: Date.parse('2026-10-06T02:00:00Z') })
  on('session.usage', () => ({ value: { context: { window: 1000000 }, rateLimits: [] } }))
  on('session.start', (_, event) => ({ cwd: event.cwd }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  const mounted = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props: {
    hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100,
    scroll: { offset: 0, bodyRows: 12 }, view: {},
  } })
  const pet = (await mounted.findAll({ type: 'Svg' })).find(item => item.props.alt === 'Claude is idle')
  expect(String(pet?.props.source).includes('x="-2" y="-2" width="104" height="22"')).toBe(false)
  expect(String(pet?.props.source).includes('viewBox="0 0 100 18"')).toBe(true)
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
  expect(svgs.map(s => s.props.alt)).toContain('Claude is idle')
  for (const card of svgs.filter(s => String(s.props.alt).includes('剩余'))) {
    expect(card.props.width).toBe(140)
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
  expect(await footer.find({ text: 'ctx17% 175k/1M' })).toBeDefined()
  await footer.unmount()
  await terminal.unmount()
  await ui.unmount()
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
