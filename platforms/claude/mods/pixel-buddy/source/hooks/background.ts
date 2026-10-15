import type { WorkState } from '../types'

let sequence = 0
export const workStamp = (after = 0) => (sequence = Math.max(sequence, after) + 1)
export const emptyWork = (epoch: number): WorkState => ({
  epoch, known: false, snapshot: 0, turnAt: 0, active: {}, closed: {}, calls: {},
})
// 旧版热重载留下的面板没有任务字段，不能据此假定后台为空。
export const panelWork = (state: { work?: WorkState }): WorkState => state.work ?? emptyWork(0)
export const hasWork = (work: WorkState) => Object.keys(work.calls).length > 0 || Object.keys(work.active).length > 0
const key = (id: string) => `task:${id}`
const validId = (id: unknown): id is string => typeof id === 'string' && /^[\w.:-]{1,160}$/.test(id)
const liveStatuses = ['running', 'pending', 'waiting']
const endedStatuses = ['completed', 'failed', 'killed', 'idle']

export function started(work: WorkState, id: unknown, at: number): WorkState {
  if (!validId(id) || at < work.epoch || (work.closed[key(id)] ?? 0) >= at || (work.active[key(id)] ?? 0) > at) return work
  const closed = { ...work.closed }
  delete closed[key(id)]
  return { ...work, active: { ...work.active, [key(id)]: at }, closed }
}

export function finished(work: WorkState, id: unknown, at: number): WorkState {
  if (!validId(id) || at < work.epoch || (work.active[key(id)] ?? 0) > at || (work.closed[key(id)] ?? 0) >= at) return work
  const active = { ...work.active }
  delete active[key(id)]
  // 保存终态序号：完成先到、启动回调后到，以及迟到的 running 快照都不能复活旧任务。
  return { ...work, active, closed: { ...work.closed, [key(id)]: at } }
}

export function reconcile(work: WorkState, tasks: unknown, at: number): WorkState {
  if (at < work.epoch || at < work.snapshot) return work
  const active: Record<string, number> = Object.fromEntries(Object.entries(work.active).filter(([, start]) => start > at))
  const known = Array.isArray(tasks) && tasks.every(task => task && validId(task.id)
    && [...liveStatuses, ...endedStatuses].includes(task.status))
  // 缺失或不完整快照不能抹掉已确认的任务，也不能冒充新的完整快照。
  if (!known) return { ...work, known: false }
  for (const task of tasks) {
    if (liveStatuses.includes(task.status) && !work.closed[key(task.id)]) {
      active[key(task.id)] = work.active[key(task.id)] ?? at
    }
  }
  return { ...work, known, snapshot: at, active }
}

// 同一会话重载仅接续已登记的后台任务；旧前台 Promise 不在新实例内继续计数。
export function resumeWork(work: WorkState, epoch: number): WorkState {
  return { ...emptyWork(epoch), active: Object.fromEntries(Object.keys(work.active).map(id => [id, epoch])) }
}

export function restoreAgents(work: WorkState, agents: unknown, at: number): WorkState {
  if (at < work.epoch || at < work.snapshot || !Array.isArray(agents)) return work
  // agent.list 不含后台 shell，只合并已核实的代理，不能把它当作全局任务快照。
  let next = work
  for (const agent of agents) {
    if (!agent || !validId(agent.id)) continue
    if (liveStatuses.includes(agent.status)) next = started(next, agent.id, at)
    else if (endedStatuses.includes(agent.status)) next = finished(next, agent.id, at)
  }
  return next
}

export function notificationTask(text: string): string | undefined {
  // 只解析宿主 task-notification 来源的外层协议；不从工具正文或用户文本推断完成。
  const envelope = text.match(/^\s*<task-notification>([\s\S]*?)<\/task-notification>/)?.[1]
  const header = envelope?.split(/<(?:summary|result|output)>/, 1)[0]
  const id = header?.match(/<task-id>([^<]+)<\/task-id>/)?.[1].trim()
  const status = header?.match(/<status>([^<]+)<\/status>/)?.[1].trim()
  return validId(id) && ['completed', 'failed', 'killed'].includes(status ?? '') ? id : undefined
}
