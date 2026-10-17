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
// 通知里的终态。stopped 是宿主续接会话时为上一个进程没留下完成记录的任务补发的，之后不会再有完成通知。
const noticeEndings = ['completed', 'failed', 'killed', 'stopped']
// 宿主的订阅类与内部维护类任务：监视（如已发布 Artifact 的评论监视，会话期间一直 running）、记忆整理、自动模式扫描、记忆导入。
// 它们不是「脚本或子代理做完会来信」的工作，也不会自己结束，计入就会让信箱一直亮着。类型取自宿主自己的类型标签表，
// 标签对不上时再按宿主生成任务 ID 的规则兜底：监视 s/m、整理 d、扫描 e、导入 n 加 8 位字母数字（脚本 b、代理 a、工作流 w 等不受影响）。
const quietTypes = ['monitor', 'monitor_ws', 'monitor_mcp', 'dream', 'auto-mode scan', 'auto_mode_scan', 'memory import', 'local_memory_import']
const quietId = /^[smden][0-9a-z]{8}$/
const MAX_LISTED = 30
// 宿主向子代理投递通知时，会在信封前加一段固定的「系统通知，非用户输入」声明，有时再包一层 <system-reminder>。
const declaration = /^\s*(?:<system-reminder>\s*)?\[SYSTEM NOTIFICATION[^\]]*\][\s\S]*?(?=<task-notification>)/

export function quietTask(task: { id?: unknown; type?: unknown }): boolean {
  return (typeof task.type === 'string' && quietTypes.includes(task.type)) || (typeof task.id === 'string' && quietId.test(task.id))
}

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
  // 每条只要求有可用的 ID 和字符串状态；状态词不认识的那一条按「未列出」处理，
  // 不能让宿主新增的一个状态词作废整份快照，导致过期的等待一直清不掉。
  const known = Array.isArray(tasks) && tasks.every(task => task && validId(task.id) && typeof task.status === 'string')
  // 缺失或不完整快照不能抹掉已确认的任务，也不能冒充新的完整快照。
  if (!known) return { ...work, known: false }
  // 记下这份快照列出的每条任务的类型，仅供 /buddy-status 对照；类型文字限长并替换异常字符。
  const listed: Record<string, string> = {}
  for (const task of tasks) {
    if (Object.keys(listed).length < MAX_LISTED) listed[task.id] = typeof task.type === 'string' ? task.type.replace(/[^\w .-]/g, '?').slice(0, 24) : '?'
    if (quietTask(task)) continue
    if (liveStatuses.includes(task.status) && !work.closed[key(task.id)]) {
      active[key(task.id)] = work.active[key(task.id)] ?? at
    }
  }
  return { ...work, known, snapshot: at, active, listed }
}

// 主回合结束后仍没返回的前台调用不会再返回（被中断，或宿主放弃了它），留着会让等待一直亮着；
// 此后新登记的调用保留。后台任务在 active 里另行跟踪，不受影响。
export function dropCalls(work: WorkState, at: number): WorkState {
  const calls = Object.fromEntries(Object.entries(work.calls).filter(([, start]) => start > at))
  return Object.keys(calls).length === Object.keys(work.calls).length ? work : { ...work, calls }
}

// 同一会话重载仅接续已登记的后台任务；旧前台 Promise 不在新实例内继续计数。
export function resumeWork(work: WorkState, epoch: number): WorkState {
  // 旧版本可能把宿主的监视类任务记进了 active；重载时不再带过去，免得要等下一份快照才清掉。
  const carried = Object.keys(work.active).filter(id => !quietTask({ id: id.replace(/^task:/, '') }))
  return { ...emptyWork(epoch), active: Object.fromEntries(carried.map(id => [id, epoch])) }
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
  // 信封必须在开头，或紧跟宿主的固定声明；声明之外的前缀一律不认。
  const envelope = text.replace(declaration, '').match(/^\s*<task-notification>([\s\S]*?)<\/task-notification>/)?.[1]
  const header = envelope?.split(/<(?:summary|result|output)>/, 1)[0]
  const id = header?.match(/<task-id>([^<]+)<\/task-id>/)?.[1].trim()
  const status = header?.match(/<status>([^<]+)<\/status>/)?.[1].trim()
  return validId(id) && noticeEndings.includes(status ?? '') ? id : undefined
}
