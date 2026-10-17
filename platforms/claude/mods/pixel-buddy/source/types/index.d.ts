export type Mood = 'idle' | 'working' | 'thinking' | 'replying' | 'asking' | 'done' | 'relax' | 'compact' | 'waiting'
  | 'unknown' | 'error' | 'aborted'
// 工作中的三种细分；只来自模型响应的块类型，不从工具名或文本内容推断。
export type StepMood = 'working' | 'thinking' | 'replying'
// 咖啡温度对应提示缓存的剩余寿命：热、过半、已过期。
export type CacheStage = 'hot' | 'warm' | 'cold'
export type WorkState = {
  epoch: number
  known: boolean
  snapshot: number
  turnAt: number
  active: Record<string, number>
  closed: Record<string, number>
  calls: Record<string, number>
  // 最近一份完整快照里每条任务的类型标签，仅供状态命令对照；旧版热重载留下的面板没有这一项。
  listed?: Record<string, string>
}
export type Limit = { kind: string; percentUsed: number; resetsAt?: string }
export type Ctx = { tokens?: number; window: number; percent?: number }
export type Compaction = { enabled: boolean | null; threshold: number | null; used: number | null }
export type PanelState = {
  sessionId?: string
  phase: Mood
  phaseAt: number
  clockAt: number
  limits: Limit[]
  compacting: number
  work: WorkState
  // 以下三项由旧版热重载留下的面板可能缺失，读取时按默认值处理。
  step?: StepMood
  asking?: number
  cache?: CacheStage
}
export type FooterState = {
  clockAt: number
  cacheAt: number | null
  context: Ctx | null
  compaction: Compaction
}

declare module 'claude-code' {
  interface PluginState {
    'pixel-buddy-sam': { panel: PanelState; footer: FooterState }
  }
}
