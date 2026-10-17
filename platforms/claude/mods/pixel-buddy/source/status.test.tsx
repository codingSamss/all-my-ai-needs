import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { PanelState } from './types'
import { emptyWork, reconcile, started } from './hooks/background'
import { describeStatus } from './hooks/status'

const props = { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100, scroll: { offset: 0, bodyRows: 12 }, view: {} }
const waitAlt = 'Claude is waiting for scripts or subagents'
const task = (id: string) => ({ id, type: 'shell', status: 'running', description: 'fixture' })
const stop = (tasks: ReturnType<typeof task>[]) => ({ stop_hook_active: false, background_tasks: tasks })
const panel = (work = emptyWork(1)): PanelState => ({ phase: 'idle', phaseAt: 0, clockAt: 0, limits: [], compacting: 0, work })
const agent = (id: string, status: string, type = 'general-purpose') => ({ id, type, status, description: 'secret-description', name: 'secret-name' })

test('尚无快照时标明未经确认，并与代理列表对照；不输出描述和名称', () => {
  const work = started(started(emptyWork(1), 'agent-one', 2), 'shell-one', 3)
  const text = describeStatus(panel(work), [agent('agent-one', 'waiting')])
  expect(text).toContain('宿主快照：没有')
  expect(text).toContain('信箱依据：在途调用 0 + 后台任务 2，主会话不工作时会显示信箱')
  expect(text).toContain('agent-one  尚无快照，未经确认  类型 未记录  代理列表：waiting')
  expect(text).toContain('shell-one  尚无快照，未经确认  类型 未记录  不在代理列表')
  expect(text).toContain('代理列表（agent.list）1 条：')
  expect(text).toContain('agent-one  waiting  general-purpose')
  expect(text).not.toContain('secret')
})

test('有快照时区分宿主确认的任务和快照之后登记的任务', () => {
  const work = reconcile(started(started(emptyWork(1), 'listed-shell', 2), 'late-shell', 10), [task('listed-shell')], 5)
  const text = describeStatus(panel({ ...work, turnAt: 4 }), [])
  expect(text).toContain('宿主快照：已拿到（序号 5，回合序号 4）')
  expect(text).toContain('listed-shell  宿主快照确认在跑  类型 shell  不在代理列表')
  expect(text).toContain('late-shell  快照之后登记，未经快照确认  类型 未记录  不在代理列表')
  expect(text).toContain('代理列表（agent.list）0 条：')
})

test('没有任务、代理列表读不到、旧版面板缺少任务字段，都能照常输出', () => {
  const idle = describeStatus(panel(), undefined)
  expect(idle).toContain('不会显示信箱')
  expect(idle).toContain('代理列表（agent.list）读取失败')
  expect(idle).not.toContain('后台任务 0 个')
  const legacy = { phase: 'idle', phaseAt: 0, clockAt: 0, limits: [], compacting: 0 } as unknown as PanelState
  expect(describeStatus(legacy, [])).toContain('宿主快照：没有')
})

test('异常字符被替换，超过 20 行只列前 20 条并注明余数', () => {
  const agents = [...Array.from({ length: 25 }, (_, index) => agent(`agent-${index}`, 'idle')), agent('bad id\n<b>', 'run\nning')]
  const text = describeStatus(panel(), agents)
  expect(text).toContain('代理列表（agent.list）26 条：')
  expect(text).toContain('另有 6 条未列出')
  expect(text).not.toContain('agent-24')
  expect(text).not.toContain('<b>')
  const crowded = Array.from({ length: 22 }, (_, index) => `shell-${index}`).reduce((work, id, index) => started(work, id, index + 2), emptyWork(1))
  expect(describeStatus(panel(crowded), [])).toContain('另有 2 条未列出')
})

async function fixture($: Engine, on: On, live: { agents?: () => unknown; known?: boolean } = {}) {
  const registered: { name: string; description: string; immediate?: true }[] = []
  const clock = mock.clock(on, { now: 100000 })
  on('session.usage', () => ({ value: { context: { window: 1000000 }, rateLimits: [] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 'fixture-session' }))
  on('agent.list', () => {
    const list = live.agents?.() ?? []
    if (list instanceof Error) throw list
    return { value: list as never }
  })
  on('command.register', (_, e) => { registered.push(e); return { value: { command: e.name } } })
  on('classic.Stop', () => ({}))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  if (live.known !== false) await $.classic.Stop(stop([]))
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const alt = async () => (await ui.findAll({ type: 'Svg' })).map(svg => svg.props.alt)
  return { clock, ui, alt, registered }
}

test('会话启动时登记 buddy-status，可在回合进行中直接运行', async ($, on) => {
  const { ui, registered } = await fixture($, on)
  expect(registered).toEqual([expect.objectContaining({ name: 'buddy-status', immediate: true })])
  expect(registered[0].description).toContain('只读')
  await ui.unmount()
})

test('buddy-status 只读：列出宿主快照确认的任务，运行前后画面与输出都不变', async ($, on) => {
  const { ui, alt } = await fixture($, on, { agents: () => [agent('sub-one', 'waiting')] })
  await $.classic.Stop(stop([task('shell-one')]))
  await ui.redraw(props)
  const before = await alt()
  expect(before).toContain(waitAlt)
  const first = await $.command.run({ command: 'buddy-status' })
  const second = await $.command.run({ command: 'buddy-status' })
  expect(second).toEqual(first)
  expect(first.text).toContain('宿主快照：已拿到')
  expect(first.text).toContain('后台任务 1 个：')
  expect(first.text).toContain('shell-one  宿主快照确认在跑  类型 shell  不在代理列表')
  // 代理列表里的等待代理不在宿主快照里，已被快照清掉；它只出现在原始列表里供核对。
  expect(first.text).toContain('sub-one  waiting  general-purpose')
  expect(first.text).not.toContain('sub-one  尚无快照')
  await ui.redraw(props)
  expect(await alt()).toEqual(before)
  await ui.unmount()
})

test('buddy-status 能看出重载后由代理列表补进、尚未被快照校正的等待', async ($, on) => {
  const { ui, alt } = await fixture($, on, { agents: () => [agent('lingering', 'waiting')], known: false })
  expect(await alt()).toContain(waitAlt)
  const result = await $.command.run({ command: 'buddy-status' })
  expect(result.text).toContain('宿主快照：没有')
  expect(result.text).toContain('lingering  尚无快照，未经确认  类型 未记录  代理列表：waiting')
  // 主会话下一次回合结束时的完整快照不再列出它，信箱随之清掉。
  await $.classic.Stop(stop([]))
  expect(await alt()).not.toContain(waitAlt)
  expect((await $.command.run({ command: 'buddy-status' })).text).not.toContain('后台任务 1 个')
  await ui.unmount()
})

test('代理列表读取失败时命令照常回答，并注明读取失败', async ($, on) => {
  const { ui } = await fixture($, on, { agents: () => new Error('fixture failure') })
  const result = await $.command.run({ command: 'buddy-status' })
  expect(result.text).toContain('代理列表（agent.list）读取失败')
  expect(result.text).toContain('不会显示信箱')
  await ui.unmount()
})

test('宿主列出但被忽略的监视类任务单独列出，并带类型，不算后台任务', async ($, on) => {
  const { ui, alt } = await fixture($, on)
  await $.classic.Stop(stop([{ ...task('shbjycjln'), type: 'monitor' }, task('shell-one')]))
  const text = (await $.command.run({ command: 'buddy-status' })).text
  expect(text).toContain('后台任务 1 个：')
  expect(text).toContain('shell-one  宿主快照确认在跑  类型 shell')
  expect(text).toContain('宿主列出但不计入等待 1 个')
  expect(text).toContain('shbjycjln  类型 monitor')
  await $.classic.Stop(stop([{ ...task('shbjycjln'), type: 'monitor' }]))
  expect(await alt()).not.toContain(waitAlt)
  expect((await $.command.run({ command: 'buddy-status' })).text).toContain('信箱依据：在途调用 0 + 后台任务 0，不会显示信箱')
  await ui.unmount()
})
