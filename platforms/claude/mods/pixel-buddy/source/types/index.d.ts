export type Mood = 'idle' | 'working' | 'done' | 'relax' | 'waiting' | 'unknown'
export type WorkState = {
  epoch: number
  known: boolean
  snapshot: number
  turnAt: number
  active: Record<string, number>
  closed: Record<string, number>
  calls: Record<string, number>
}
export type Limit = { kind: string; percentUsed: number; resetsAt?: string }
export type Ctx = { tokens?: number; window: number; percent?: number; compactWindow?: number }
export type PanelState = {
  phase: Mood
  phaseAt: number
  clockAt: number
  limits: Limit[]
  work: WorkState
}
export type FooterState = {
  clockAt: number
  cacheAt: number | null
  context: Ctx | null
}

declare module 'claude-code' {
  interface PluginState {
    'pixel-buddy-sam': { panel: PanelState; footer: FooterState }
  }
}
