export type Mood = 'idle' | 'working' | 'done' | 'relax'
export type Limit = { kind: string; percentUsed: number; resetsAt?: string }
export type Ctx = { tokens?: number; window: number; percent?: number }
export type Telemetry = {
  phase: Mood
  phaseAt: number
  clockAt: number
  cacheAt: number | null
  context: Ctx | null
  limits: Limit[]
}

declare module 'claude-code' {
  interface PluginState {
    'pixel-buddy-sam': { telemetry: Telemetry; animationAt: number }
  }
}
