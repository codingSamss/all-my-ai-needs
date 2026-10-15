import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'
import { emptyWork, finished, hasWork, notificationTask, reconcile, started, panelWork } from './hooks/background'

const props = { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 100, scroll: { offset: 0, bodyRows: 12 }, view: {} }
const waitAlt = 'Claude is waiting for scripts or subagents'
const unknownAlt = 'Claude task status is unknown'
const task = (id: string, type = 'shell') => ({ id, type, status: 'running', description: 'fixture' })
const stop = (tasks: ReturnType<typeof task>[]) => ({ stop_hook_active: false, background_tasks: tasks })
const complete = (agentId?: string) => ({ turnId: 'turn', agentId, answer: '', durationMs: 1000, isAborted: false, usage: null })
const notice = (id: string, status = 'completed') => `<task-notification>\n<task-id>${id}</task-id>\n<status>${status}</status>\n<summary>fixture</summary>\n</task-notification>`
const spawn = { tool_use_id: 'spawn', prompt: 'fixture', description: 'fixture', subagentType: 'general-purpose',
  provider: { plugin: 'engine', tier: 'core' as const }, parentModel: 'fixture-model', background: true, fork: false }

async function fixture($: Engine, on: On, known = true) {
  const clock = mock.clock(on, { now: 100000 })
  on('session.usage', () => ({ value: { context: { window: 1000000 }, rateLimits: [
    { kind: 'five_hour', percentUsed: 65, resetsAt: new Date(100000 + 3600000).toISOString() },
    { kind: 'seven_day', percentUsed: 20, resetsAt: new Date(100000 + 86400000).toISOString() },
  ] } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('classic.Stop', () => ({}))
  on('classic.SubagentStop', () => ({}))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('prompt.submit', (_, e) => ({ text: e.text, origin: e.origin }))
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  if (known) await $.classic.Stop(stop([]))
  const ui = await $.ui.mount({ plugin: 'pixel-buddy-sam', surface: 'desktop', component: 'AbovePrompt', props })
  const alt = async () => (await ui.findAll({ type: 'Svg' })).map(svg => svg.props.alt)
  return { clock, ui, alt }
}

test('前台脚本未返回时显示等待，结束后恢复，原工具结果透传', async ($, on) => {
  const output = { stdout: 'fixture', stderr: '', interrupted: false }
  on('tool.call', { tool: 'Bash' }, async () => { await clock.sleep(2000); return { result: output } })
  const { clock, ui, alt } = await fixture($, on)
  await ui.redraw({ ...props, isWorking: true })
  const pending = $.tool.call({ tool: 'Bash', tool_use_id: 'shell-sync', command: 'fixture' })
  await clock.settle()
  expect(await alt()).toContain(waitAlt)
  const cards = (await ui.findAll({ type: 'Svg' })).filter(svg => String(svg.props.alt).includes('剩余'))
  expect(cards.length).toBe(2)
  expect(String(cards[0].props.source)).toContain('translate(0 22)')
  expect(String(cards[0].props.source)).toContain('translate(0 38)')
  await clock.advance(2000)
  expect((await pending).result).toEqual(output)
  expect(await alt()).toContain('Claude is working')
  await ui.unmount()
})

test('脚本与 subagent 并行：主回复结束后继续等待，最后一项结束才休息', async ($, on) => {
  on('tool.call', { tool: 'Bash' }, () => ({ result: { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'shell-bg' } }))
  on('agent.spawn', () => ({ model: 'fixture-model', agentId: 'agent-bg' }))
  const { ui, alt } = await fixture($, on)
  await $.turn.start({ turnId: 'turn', text: '' })
  await $.tool.call({ tool: 'Bash', tool_use_id: 'shell', command: 'fixture', run_in_background: true })
  await $.agent.spawn(spawn)
  await $.classic.Stop(stop([task('shell-bg'), task('agent-bg', 'subagent')]))
  await $.turn.complete(complete())
  expect(await alt()).toContain(waitAlt)
  await $.turn.complete(complete('agent-bg'))
  await $.turn.complete(complete('agent-bg'))
  expect(await alt()).toContain(waitAlt)
  await $.prompt.submit({ text: notice('shell-bg'), wait: false, origin: { kind: 'composer' } })
  expect(await alt()).toContain(waitAlt)
  await $.prompt.submit({ text: notice('shell-bg'), wait: false, origin: { kind: 'task-notification' } })
  expect(await alt()).toContain('Claude is relaxing')
  expect(await alt()).not.toContain('Claude is celebrating')
  await $.classic.Stop(stop([task('shell-bg'), task('agent-bg', 'subagent')]))
  expect(await alt()).not.toContain(waitAlt)
  await ui.unmount()
})

test('同步 Agent 调用期间等待；子代理比启动回调先结束不会被复活', async ($, on) => {
  on('agent.spawn', async () => { await clock.sleep(1000); return { model: 'fixture-model', agentId: 'fast-agent' } })
  on('tool.call', { tool: 'Agent' }, async () => {
    await $.agent.spawn({ ...spawn, background: false })
    return { result: { agentId: 'fast-agent', content: [], totalDurationMs: 1000, totalTokens: 0, totalToolUseCount: 0, usage: {} } }
  })
  const { clock, ui, alt } = await fixture($, on)
  const pending = $.tool.call({ tool: 'Agent', tool_use_id: 'agent-call', prompt: 'fixture', description: 'fixture' })
  await clock.settle()
  expect(await alt()).toContain(waitAlt)
  await $.turn.complete(complete('fast-agent'))
  expect(await alt()).toContain(waitAlt)
  await clock.advance(1000)
  await pending
  expect(await alt()).not.toContain(waitAlt)
  await ui.unmount()
})

test('重载先未知；完整快照恢复后台等待，子代理 Stop 快照仍按整个会话校正', async ($, on) => {
  const { ui, alt } = await fixture($, on, false)
  expect(await alt()).toContain(unknownAlt)
  await $.classic.Stop(stop([task('nested-shell')]))
  expect(await alt()).toContain(waitAlt)
  await $.classic.SubagentStop({ ...stop([task('nested-shell')]), agent_id: 'child', agent_type: 'general-purpose', agent_transcript_path: '' })
  await $.turn.complete(complete('child'))
  expect(await alt()).toContain(waitAlt)
  await $.classic.Stop({ stop_hook_active: false })
  expect(await alt()).toContain(unknownAlt)
  await $.classic.Stop(stop([]))
  expect(await alt()).not.toContain(unknownAlt)
  expect(await alt()).not.toContain(waitAlt)
  await ui.unmount()
})

for (const status of ['completed', 'failed', 'killed']) test(`后台 ${status} 通知在子代理日志入口送达也能结束等待`, async ($, on) => {
  const { ui, alt } = await fixture($, on)
  await $.classic.Stop(stop([task('shell-result')]))
  const message = { type: 'user' as const, role: 'user' as const, content: [{ type: 'text' as const, text: notice('shell-result', status) }] }
  await $.session.append({ door: 'submit', origin: { kind: 'task-notification' }, uuid: 'fixture-row', agentId: 'child', message })
  expect(await alt()).not.toContain(waitAlt)
  expect(await alt()).not.toContain('Claude is celebrating')
  await ui.unmount()
})

test('成功停止采用结果 ID，停止失败或普通工具报错不能伪造后台完成', async ($, on) => {
  let failed = true
  on('tool.call', { tool: 'TaskStop' }, () => failed ? { deny: 'fixture refusal' }
    : { result: { message: 'stopped', task_id: 'canonical-agent', task_type: 'local_agent' } })
  const { ui, alt } = await fixture($, on)
  await $.classic.Stop(stop([task('canonical-agent', 'subagent')]))
  await $.tool.call({ tool: 'TaskStop', task_id: 'agent-name' })
  expect(await alt()).toContain(waitAlt)
  failed = false
  await $.tool.call({ tool: 'TaskStop', task_id: 'agent-name' })
  expect(await alt()).not.toContain(waitAlt)
  await ui.unmount()
})

test('工具拒绝和报错均释放等待；绑定最终回复的短命 shell 不留下后台残项', async ($, on) => {
  let outcome = 'denied'
  on('tool.call', { tool: 'Bash' }, () => {
    if (outcome === 'denied') return { deny: 'fixture refusal' }
    if (outcome === 'error') return { result: { stdout: '', stderr: 'fixture failure', interrupted: true }, isError: true }
    return { result: { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'short-shell', backgroundEndsWithFinalResponse: true } }
  })
  const { ui, alt } = await fixture($, on)
  for (outcome of ['denied', 'error', 'short']) {
    await $.tool.call({ tool: 'Bash', command: 'fixture', tool_use_id: outcome }).catch(() => {})
    expect(await alt()).not.toContain(waitAlt)
  }
  await ui.unmount()
})

test('长脚本模拟一小时仍等待且复用 SVG，不因超时猜测成功', async ($, on) => {
  const { clock, ui, alt } = await fixture($, on)
  await $.classic.Stop(stop([task('long-script')]))
  const before = (await ui.findAll({ type: 'Svg' })).find(svg => svg.props.alt === waitAlt)?.props.source
  await clock.advance(3600000)
  expect(await alt()).toContain(waitAlt)
  expect((await ui.findAll({ type: 'Svg' })).find(svg => svg.props.alt === waitAlt)?.props.source).toBe(before)
  await ui.unmount()
})

test('中断或缺少本轮快照时显示未知；重载前的旧脚本回调不污染新状态', async ($, on) => {
  on('tool.call', { tool: 'Bash' }, async () => { await clock.sleep(1000); return { result: { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'old-shell' } } })
  const { clock, ui, alt } = await fixture($, on)
  const pending = $.tool.call({ tool: 'Bash', command: 'fixture' })
  await clock.settle()
  await $.session.start({ cwd: '/project', surface: 'desktop', isInteractive: true })
  await clock.advance(1000)
  await pending
  expect(await alt()).toContain(unknownAlt)
  await $.classic.Stop(stop([]))
  await $.turn.start({ turnId: 'turn', text: '' })
  await $.turn.complete(complete())
  expect(await alt()).toContain(unknownAlt)
  await $.classic.Stop(stop([task('live-shell')]))
  await $.turn.complete({ ...complete(), isAborted: true })
  expect(await alt()).toContain(unknownAlt)
  await ui.unmount()
})

test('乱序快照、终态重复和同 ID 新一轮运行保持一致', () => {
  let work = started(emptyWork(1), 'a', 2)
  work = reconcile(work, [task('a')], 3)
  work = finished(work, 'a', 4)
  work = reconcile(work, [task('a')], 5)
  expect(hasWork(work)).toBe(false)
  work = started(work, 'a', 6)
  expect(hasWork(work)).toBe(true)
  work = reconcile(work, [], 3)
  expect(hasWork(work)).toBe(true)
  work = reconcile(work, [], 7)
  expect(hasWork(work)).toBe(false)
  expect(reconcile(work, [{ id: 'x', status: 'new-unknown-state' }], 8).known).toBe(false)
  expect(notificationTask('User says ' + notice('a'))).toBeUndefined()
  expect(notificationTask(notice('a', 'running'))).toBeUndefined()
})

test('旧版缺少任务字段时保持未知，首份快照恢复任务状态', () => {
  const work = panelWork({})
  expect(work.known).toBe(false)
  const restored = reconcile(work, [task('resumed-shell')], 1)
  expect(restored.known).toBe(true)
  expect(hasWork(restored)).toBe(true)
})

test('后台 shell 完成通知早于启动返回时，迟到结果不重新开启沙漏', async ($, on) => {
  on('tool.call', { tool: 'Bash' }, async () => {
    await clock.sleep(1000)
    return { result: { stdout: '', stderr: '', interrupted: false, backgroundTaskId: 'fast-shell' } }
  })
  const { clock, ui, alt } = await fixture($, on)
  const pending = $.tool.call({ tool: 'Bash', command: 'fixture', tool_use_id: 'fast' })
  await clock.settle()
  await $.prompt.submit({ text: notice('fast-shell'), wait: false, origin: { kind: 'task-notification' } })
  expect(await alt()).toContain(waitAlt)
  await clock.advance(1000)
  await pending
  expect(await alt()).not.toContain(waitAlt)
  await ui.unmount()
})
