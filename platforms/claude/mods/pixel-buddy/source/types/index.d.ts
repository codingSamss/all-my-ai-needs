export type Mood = 'idle' | 'working' | 'done' | 'relax'
export type Limit = { kind: string; percentUsed: number; resetsAt?: string }
export type Ctx = { tokens?: number; window: number; percent?: number }
export type PanelState = {
  phase: Mood
  phaseAt: number
  clockAt: number
  limits: Limit[]
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
