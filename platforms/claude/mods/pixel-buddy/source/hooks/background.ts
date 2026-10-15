import type { WorkState } from '../types'

let sequence = 0
export const workStamp = () => ++sequence
export const emptyWork = (epoch: number): WorkState => ({
  epoch, known: false, snapshot: 0, turnAt: 0, active: {}, closed: {}, calls: {},
})
// 旧版热重载留下的面板没有任务字段，不能据此假定后台为空。
export const panelWork = (state: { work?: WorkState }): WorkState => state.work ?? emptyWork(0)
export const hasWork = (work: WorkState) => Object.keys(work.calls).length > 0 || Object.keys(work.active).length > 0
const key = (id: string) => `task:${id}`
const validId = (id: unknown): id is string => typeof id === 'string' && /^[\w.:-]{1,160}$/.test(id)

export function started(work: WorkState, id: unknown, at: number): WorkState {
  if (!validId(id) || at < work.epoch || (work.closed[key(id)] ?? 0) >= at) return work
  const closed = { ...work.closed }
  delete closed[key(id)]
  return { ...work, active: { ...work.active, [key(id)]: at }, closed }
}

export function finished(work: WorkState, id: unknown, at: number): WorkState {
  if (!validId(id) || at < work.epoch || (work.active[key(id)] ?? 0) > at) return work
  const active = { ...work.active }
  delete active[key(id)]
  // 保存终态序号：完成先到、启动回调后到，以及迟到的 running 快照都不能复活旧任务。
  return { ...work, active, closed: { ...work.closed, [key(id)]: at } }
}

export function reconcile(work: WorkState, tasks: unknown, at: number): WorkState {
  if (at < work.epoch || at < work.snapshot) return work
  const active: Record<string, number> = Object.fromEntries(Object.entries(work.active).filter(([, start]) => start > at))
  const known = Array.isArray(tasks) && tasks.every(task => task && validId(task.id)
    && ['running', 'pending', 'completed', 'failed', 'killed'].includes(task.status))
  // 缺失不等于 []。无法取得完整快照时丢弃旧推断，保留确实尚未返回的前台调用。
  if (known) for (const task of tasks) {
    if (['running', 'pending'].includes(task.status) && !work.closed[key(task.id)]) {
      active[key(task.id)] = work.active[key(task.id)] ?? at
    }
  }
  return { ...work, known, snapshot: at, active }
}

export function notificationTask(text: string): string | undefined {
  // 只解析宿主 task-notification 来源的外层协议；不从工具正文或用户文本推断完成。
  const envelope = text.match(/^\s*<task-notification>([\s\S]*?)<\/task-notification>/)?.[1]
  const header = envelope?.split(/<(?:summary|result|output)>/, 1)[0]
  const id = header?.match(/<task-id>([^<]+)<\/task-id>/)?.[1].trim()
  const status = header?.match(/<status>([^<]+)<\/status>/)?.[1].trim()
  return validId(id) && ['completed', 'failed', 'killed'].includes(status ?? '') ? id : undefined
}
