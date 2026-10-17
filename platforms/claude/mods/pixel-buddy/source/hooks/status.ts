import type { EngineInterface } from 'claude-code'
import type { PanelState } from '../types'
import { hasWork, panelWork, quietTask } from './background'

const MAX_ROWS = 20

// 只打印 ID、状态和类型，不带代理描述与名称，避免把任务内容写进对话。
const safe = (value: unknown, max = 48) => typeof value === 'string' ? value.replace(/[^\w.:@ -]/g, '?').slice(0, max) : '?'

// 把插件记着的等待状态摊开：信箱到底依据哪些 ID、有没有被宿主快照确认过、代理列表里它们是什么状态。
export function describeStatus(state: PanelState, agents: unknown): string {
  const work = panelWork(state)
  const active = Object.entries(work.active).sort(([, a], [, b]) => a - b)
  const calls = Object.keys(work.calls).length
  const quiet = Object.entries(work.listed ?? {}).filter(([id, type]) => quietTask({ id, type }))
  const list = Array.isArray(agents) ? agents.filter(agent => agent && typeof agent === 'object') : undefined
  const listed = new Map((list ?? []).map(agent => [safe(agent.id, 160), safe(agent.status)]))
  const more = (total: number) => total > MAX_ROWS ? [`  … 另有 ${total - MAX_ROWS} 条未列出`] : []
  const confirmed = (start: number) => work.known && start <= work.snapshot
    ? '宿主快照确认在跑' : work.known ? '快照之后登记，未经快照确认' : '尚无快照，未经确认'
  return [
    'Pixel Buddy 状态（只读）',
    `阶段 ${safe(state.phase)} · 压缩 ${state.compacting ?? 0} · 提问 ${state.asking ?? 0}`,
    work.known
      ? `宿主快照：已拿到（序号 ${work.snapshot}，回合序号 ${work.turnAt}）`
      : '宿主快照：没有（重载或新会话后，要等主回合结束才有）',
    `信箱依据：在途调用 ${calls} + 后台任务 ${active.length}，${hasWork(work) ? '主会话不工作时会显示信箱' : '不会显示信箱'}`,
    ...(active.length ? [`后台任务 ${active.length} 个：`] : []),
    ...active.slice(0, MAX_ROWS).map(([id, start]) => {
      const task = safe(id.replace(/^task:/, ''), 160)
      return `  ${task}  ${confirmed(start)}  类型 ${work.listed?.[task] === undefined ? '未记录' : safe(work.listed[task], 24)}  ${listed.has(task) ? `代理列表：${listed.get(task)}` : '不在代理列表'}`
    }),
    ...more(active.length),
    ...(quiet.length ? [`宿主列出但不计入等待 ${quiet.length} 个（订阅或内部维护类，不会自己结束）：`] : []),
    ...quiet.slice(0, MAX_ROWS).map(([id, type]) => `  ${safe(id, 160)}  类型 ${safe(type, 24)}`),
    ...more(quiet.length),
    list ? `代理列表（agent.list）${list.length} 条：` : '代理列表（agent.list）读取失败',
    ...(list ?? []).slice(0, MAX_ROWS).map(agent => `  ${safe(agent.id, 160)}  ${safe(agent.status)}  ${safe(agent.type)}${agent.parentId ? '  子代理' : ''}`),
    ...more(list?.length ?? 0),
    `已收到终态的任务 ${Object.keys(work.closed).length} 个`,
    '宿主真实在途的任务以该会话的 /tasks 为准。',
  ].join('\n')
}

// 命令登记必须放在 register.tsx 唯一的 session.start 钩子里（宿主不允许同一事件无匹配地重复登记）；
// 命令本身也由 register.tsx 回答（读取面板状态的 $ 只能在那里使用）。它只读：不改状态、不重载、不轮询。
export async function declareStatus($: EngineInterface) {
  try {
    // immediate：状态异常时多半正处在回合中，不必等回合结束；命令只读，不依赖回合状态。
    await $.command.register({ name: 'buddy-status', description: '只读：显示 Pixel Buddy 记着的后台任务与代理列表', immediate: true })
  } catch { /* 注册失败只是少一个诊断入口，不能影响动画。 */ }
}
