// SPDX-License-Identifier: MIT
// 基础场景摘自 pixel-at-work，版权及固定提交见 scene-NOTICES.txt；等候沙漏为独立实现。
// 仅移植绘图；不引入上游工具分类、结果猜测、节日、轮询或事件钩子。
import type { Mood } from '../types'
export const DONE_SECONDS = 6.5
export const SCENE_WIDTH = 512
export const SCENE_HEIGHT = 54
const STAGE = 80
const W = SCENE_WIDTH / 2
const H = SCENE_HEIGHT / 2

const C = {
  sky: '#161a2b', star: '#4a5578', starHi: '#8b97c4', floor: '#262c44', floorTop: '#39426a',
  o: '#d97757', ol: '#f2b49b', eye: '#2b1b17', white: '#f5f5f5', paper: '#f7f3e8', paperShade: '#c8bfa9',
  ink: '#374151', math: '#2563eb', red: '#ef4444', green: '#4ade80', amber: '#fbbf24', blue: '#60a5fa',
  steel: '#39404f', steelHi: '#59617a', slot: '#232835', screen: '#0b1020', bezel: '#4b5563', glow: '#93c5fd',
  wood: '#8b5a3c', grass: '#22c55e', grassDark: '#15803d', purple: '#a78bfa', gray: '#9aa3b5', cloud: '#e5e7eb',
}
type Pal = Record<string, string>

function rect(x: number, y: number, w: number, h: number, c: string): string {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c}"/>`
}

/** Rows of palette letters ('.' is empty) as runs of rectangles at (x, y). */
function sprite(rows: string[], pal: Pal, x = 0, y = 0): string {
  let out = ''
  rows.forEach((row, j) => {
    let i = 0
    while (i < row.length) {
      const ch = row[i]
      if (!pal[ch]) {
        i += 1
        continue
      }
      let k = i
      while (k < row.length && row[k] === ch) k += 1
      out += rect(x + i, y + j, k - i, 1, pal[ch])
      i = k
    }
  })
  return out
}


function frames(parts: string[], dur: number, begin = 0): string {
  return parts
    .map((p, i) => {
      const values = parts.map((_, j) => (j === i ? '1' : '0')).join(';')
      return `<g opacity="${i === 0 ? 1 : 0}"><animate attributeName="opacity" values="${values}" dur="${dur}s"` +
        ` begin="${-begin}s" calcMode="discrete" repeatCount="indefinite"/>${p}</g>`
    })
    .join('')
}


function path(content: string, pts: Array<[number, number]>, dur: number, begin = 0): string {
  const values = pts.map(([x, y]) => `${x} ${y}`).join(';')
  return `<g transform="translate(${pts[0][0]} ${pts[0][1]})"><animateTransform attributeName="transform"` +
    ` type="translate" values="${values}" dur="${dur}s" begin="${-begin}s" calcMode="discrete"` +
    ` repeatCount="indefinite"/>${content}</g>`
}

function line(x0: number, y0: number, x1: number, y1: number, n: number): Array<[number, number]> {
  return Array.from({ length: n + 1 }, (_, i) => [
    Math.round(x0 + ((x1 - x0) * i) / n),
    Math.round(y0 + ((y1 - y0) * i) / n),
  ])
}


function crect(x: number, y: number, w: number, h: number, cls: string, fill: string, opacity = 1): string {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}"` +
    `${opacity < 1 ? ` fill-opacity="${opacity}"` : ''} class="${cls}"/>`
}

// 同一份图随宿主 color-scheme 换色；仅日月和云星分组显隐，不需要读配置或增加计时器。
const P = {
  leaf: 'var(--pb-leaf,#166534)', house: 'var(--pb-house,#475569)',
  window: 'var(--pb-window,#fde68a)', dimWindow: 'var(--pb-window-dim,#3a4266)',
  building: 'var(--pb-building,#262d48)', buildingSide: 'var(--pb-building-side,#303952)',
  hill: 'var(--pb-hill,#1f3447)', sea: 'var(--pb-sea,#1d3557)', wave: 'var(--pb-wave,#457b9d)',
  lamp: 'var(--pb-lamp,#fde68a)', tower: 'var(--pb-tower,#9aa3b5)', towerTop: 'var(--pb-tower-top,#cbd5e1)',
}
const THEME = `<style>
.pb-wait-static{display:none}
@media(prefers-reduced-motion:reduce){.pb-wait-motion{display:none}.pb-wait-static{display:inline}}
.pb-day{display:none}.pb-night{display:inline}
.st{fill:#555b6c}.sh{fill:#a5afc4}
.fl{fill:#808080;fill-opacity:.10}.ft{fill:#808080;fill-opacity:.35}
@media (prefers-color-scheme:light){
  .pb-day{display:inline}.pb-night{display:none}
  .pb-scene{--pb-leaf:#3b8749;--pb-house:#b6c2c8;--pb-window:#81b7cf;--pb-window-dim:#81b7cf;
    --pb-building:#91aabd;--pb-building-side:#738fa7;--pb-hill:#7aa38d;--pb-sea:#9bcad7;
    --pb-wave:#d4edf0;--pb-lamp:#c5c5b6;--pb-tower:#879dac;--pb-tower-top:#b7c5ce}
  .fl{fill:#87a882;fill-opacity:.12}.ft{fill:#73946e;fill-opacity:.45}
}
</style>`

function sky(w: number): string {
  let stars = ''
  for (let x = 2, i = 0; x < w; x += 5 + ((x * 7) % 5), i += 1) {
    const y = 1 + ((x * 13 + i * 5) % 13)
    stars += i % 3 === 0
      ? frames([crect(x, y, 1, 1, 'sh', '#a5afc4'), crect(x, y, 1, 1, 'st', '#555b6c')], 1.6 + (i % 5) * 0.3, (i % 4) * 0.2)
      : crect(x, y, 1, 1, 'st', '#555b6c')
  }
  const moon = sprite(['..MMMM', '.MMM..', 'MMM...', 'MMM...', '.MMM..', '..MMMM'], { M: '#f5e6b3' }, 31, 2)
  const sun = sprite(['...R...', '.R...R.', '..SSS..', 'RSSSSSR', '..SSS..', '.R...R.', '...R...'],
    { R: '#dfb755', S: '#efc45f' }, 31, 1)
  const cloud = sprite(['...WWWW...', '.WWWWWWWW.', 'WWWWWWWWWW', '.SSSSSSSS.'], { W: '#d8e4e8', S: '#c1d5de' })
  // 云只在两侧天空缓慢移动，不遮住工作屏幕；窄布局照旧裁去两侧景物。
  const clouds = path(cloud, [[54, 3], [55, 3], [56, 3], [55, 3]], 16) +
    path(cloud, [[200, 5], [201, 5], [202, 5], [201, 5]], 19)
  return `<g class="pb-night">${stars}${moon}</g><g class="pb-day">${sun}${clouds}</g>`
}

function backdrop(w: number): string {
  return sky(w) + crect(0, 24, w, 4, 'fl', '#808080', 0.1) + crect(0, 24, w, 1, 'ft', '#808080', 0.35)
}


const BODY = [
  '..LOOOOOOO..',
  '.OOOOOOOOOO.',
  '.OOOOOOOOOO.',
  '.OOOOOOOOOO.',
  'OOOOOOOOOOOO',
  'OOOOOOOOOOOO',
  '.OOOOOOOOOO.',
  '.OOOOOOOOOO.',
]
const LEGS_A = ['.O.O....O.O.', '.O.O....O.O.']
const LEGS_B = ['..O.O..O.O..', '..O.O..O.O..']
const BODY_PAL: Pal = { O: C.o, L: C.ol }

type CritterMood = 'awake' | 'walk' | 'asleep' | 'reading' | 'typing' | 'hop' | 'panic' | 'waiting' | 'still'

function critter(x: number, y: number, mood: CritterMood = 'awake'): string {
  let s = sprite(BODY, BODY_PAL, x, y)
  const legs = (rows: string[]) => sprite(rows, BODY_PAL, x, y + 8)
  s += mood === 'walk' || mood === 'panic' ? frames([legs(LEGS_A), legs(LEGS_B)], mood === 'panic' ? 0.25 : 0.5) : legs(LEGS_A)
  const open = rect(x + 3, y + 2, 1, 2, C.eye) + rect(x + 8, y + 2, 1, 2, C.eye)
  const shut = rect(x + 2, y + 3, 2, 1, C.eye) + rect(x + 8, y + 3, 2, 1, C.eye)
  if (mood === 'asleep') s += shut
  else if (mood === 'panic') {
    // eyes wide, mouth open
    s += rect(x + 2, y + 1, 2, 2, C.white) + rect(x + 3, y + 2, 1, 1, C.eye) + rect(x + 8, y + 1, 2, 2, C.white) +
      rect(x + 8, y + 2, 1, 1, C.eye) + rect(x + 5, y + 4, 2, 2, C.eye)
  } else if (mood === 'reading' || mood === 'waiting') {
    s += path(rect(3, 2, 1, 2, C.eye) + rect(8, 2, 1, 2, C.eye),
      [[x, y], [x + 1, y], [x + 1, y], [x, y]], mood === 'waiting' ? 6 : 2.4)
  } else if (mood === 'still') s += open
  else s += frames([open, open, open, open, open, open, open, shut], 3.2)
  if (mood === 'typing') s += frames([rect(x + 12, y + 4, 2, 1, C.o), rect(x + 12, y + 5, 2, 1, C.o)], 0.3)
  if (mood === 'waiting') s += frames(['', rect(x + 11, y + 9, 1, 1, C.o)], 1.6)
  return mood === 'hop' ? path(s.replace(/x="(\d+)"/g, (_, v) => `x="${Number(v) - x}"`).replace(/y="(\d+)"/g, (_, v) => `y="${Number(v) - y}"`), [[x, y], [x, y - 2], [x, y - 3], [x, y - 2], [x, y], [x, y]], 0.9) : s
}


function scCode(): string {
  let s = critter(3, 14, 'typing')
  s += rect(20, 3, 40, 17, C.bezel) + rect(21, 4, 38, 14, C.screen) + rect(37, 20, 6, 2, C.bezel) + rect(33, 22, 14, 1, C.gray)
  const colors = ['#c084fc', '#86efac', '#93c5fd', '#fca5a5', '#d1d5db', '#fde68a']
  // Line i of the 8-line loop, drawn on screen row r (7 rows fit); one frame per scroll step, no clipping needed.
  const line = (i: number, r: number): string => {
    const y = 5 + r * 2
    const indent = [0, 2, 4, 4, 2, 4, 6, 0][i]
    return rect(23 + indent, y, 4 + ((i * 7) % 9), 1, colors[i % colors.length]) +
      rect(28 + indent + ((i * 7) % 9), y, 3 + ((i * 5) % 7), 1, colors[(i + 3) % colors.length])
  }
  const pages = Array.from({ length: 8 }, (_, f) => {
    let p = ''
    for (let r = 0; r < 7; r += 1) p += line((f + r) % 8, r)
    return p + rect(23 + [0, 2, 4, 4, 2, 4, 6, 0][(f + 6) % 8] + 18, 17, 1, 1, C.white)
  })
  s += frames(pages, 2.4)
  return s
}


function scSleep(): string {
  let s = critter(30, 14, 'asleep')
  const z = sprite(['ZZZZ', '..Z.', '.Z..', 'ZZZZ'], { Z: C.glow })
  for (let i = 0; i < 3; i += 1) s += path(z, line(44, 13, 52, 1, 6), 2.4, i * 0.8)
  s += rect(60, 18, 6, 6, C.cloud) + rect(66, 19, 2, 1, C.cloud) + rect(67, 20, 1, 2, C.cloud) + rect(66, 22, 2, 1, C.cloud) + rect(61, 18, 4, 1, '#7c4a2d')
  s += frames([rect(62, 15, 1, 2, C.gray) + rect(63, 13, 1, 2, C.gray), rect(63, 15, 1, 2, C.gray) + rect(62, 13, 1, 2, C.gray)], 1.0)
  return s
}


function scParty(): string {
  let s = critter(34, 14, 'hop')
  const colors = ['#f472b6', '#60a5fa', '#fbbf24', '#4ade80', '#a78bfa', '#f87171']
  for (let i = 0; i < 20; i += 1) {
    const x = 3 + ((i * 37) % 75)
    const c = colors[i % colors.length]
    const dur = 1.6 + ((i * 7) % 5) * 0.25
    s += path(frames([rect(0, 0, 1, 2, c), rect(0, 0, 2, 1, c)], 0.3), line(x, -2, x + ((i % 3) - 1) * 3, 23, 12), dur, (i * 0.37) % dur)
  }
  return s
}


function scIdle(): string {
  let s = critter(26, 14)
  s += rect(44, 18, 16, 2, C.wood) + rect(46, 20, 1, 4, C.wood) + rect(57, 20, 1, 4, C.wood)
  s += rect(49, 13, 6, 5, C.white) + rect(55, 14, 2, 1, C.white) + rect(56, 15, 1, 1, C.white) + rect(55, 16, 2, 1, C.white) + rect(50, 13, 4, 1, '#7c4a2d')
  const steam = (o: number) => rect(50 + o, 10, 1, 2, C.gray) + rect(51 - o, 8, 1, 2, C.gray) + rect(52 + o, 6, 1, 2, C.gray)
  s += frames([steam(0), steam(1)], 1.0)
  s += rect(65, 19, 6, 5, '#b45309') + sprite(['.G.G.', 'GGGGG', '.GGG.', '..G..'], { G: C.grass }, 65, 15)
  return s
}

// 沙漏只表示仍在等结果，循环的沙量不编码完成比例或预计剩余时间。
function hourglass(phase: number, unknown = false): string {
  const wood = unknown ? C.gray : C.wood, sand = unknown ? C.gray : '#d4a23b'
  let s = rect(0, 0, 11, 2, wood) + rect(0, 14, 11, 2, wood)
  s += sprite(['G.......G', 'G.......G', '.G.....G.', '..G...G..', '...G.G...', '....G....',
    '...G.G...', '..G...G..', '.G.....G.', 'G.......G', 'G.......G', 'G.......G'],
  { G: unknown ? '#a3a3a0' : '#bad4d6' }, 1, 2)
  if (phase === 0) s += rect(3, 3, 5, 1, sand) + rect(4, 4, 3, 2, sand) + rect(5, 6, 1, 1, sand) + rect(5, 13, 1, 1, sand)
  if (phase === 1) s += rect(4, 4, 3, 2, sand) + rect(5, 6, 1, 1, sand) + rect(3, 13, 5, 1, sand) + rect(4, 12, 3, 1, sand)
  if (phase === 2) s += rect(5, 6, 1, 1, sand) + rect(2, 13, 7, 1, sand) + rect(3, 12, 5, 1, sand) + rect(4, 11, 3, 1, sand)
  if (phase === 3) s += rect(2, 12, 7, 2, sand) + rect(3, 11, 5, 1, sand) + rect(4, 10, 3, 1, sand)
  return s
}

function scWaiting(): string {
  const steps = Array.from({ length: 24 }, (_, i) => {
    const glass = hourglass(Math.min(3, Math.floor(i / 6)))
    return i < 22 ? glass + rect(5, 8 + i % 3, 1, 1, '#d4a23b')
      : `<g transform="rotate(${i === 22 ? 90 : 180} 6 8)">${glass}</g>`
  })
  const table = rect(44, 22, 17, 2, C.wood)
  return table + `<g class="pb-wait-motion">${critter(22, 14, 'waiting')}<g transform="translate(47 6)">${frames(steps, 6)}</g></g>` +
    `<g class="pb-wait-static">${critter(22, 14, 'still')}<g transform="translate(47 6)">${hourglass(1)}</g></g>`
}

function scUnknown(): string {
  return critter(22, 14, 'still') + `<g transform="translate(47 6)">${hourglass(1, true)}</g>` +
    rect(44, 22, 17, 2, C.gray) + sprite(['.QQQ.', 'Q...Q', '....Q', '...Q.', '..Q..', '.....', '..Q..'], { Q: C.gray }, 34, 3)
}


const TREE = sprite([
  '..GGRGG..',
  '.GRGGGRG.',
  'GGGGRGGGG',
  'GRGGGGGRG',
  '.GGGRGGG.',
  '..GGGGG..',
  '....T....',
  '....T....',
  '...TT....',
  '....T....',
], { G: P.leaf, R: '#dc2626', T: '#7c4a2d' }, 0, 14)
const HOUSE = sprite([
  '.....RR.....',
  '....RRRR....',
  '...RRRRRR...',
  '..RRRRRRRR..',
  '.RRRRRRRRRR.',
  '.WWWWWWWWWW.',
  '.WYYWWWDDWW.',
  '.WYYWWWDDWW.',
  '.WWWWWWDDWW.',
], { R: '#7c2d12', W: P.house, Y: P.window, D: '#475569' }, 0, 15)
const LAMP = sprite(['YYY', '.L.', '.L.', '.L.', '.L.', '.L.', '.L.', '.L.', '.L.', 'LLL'], { Y: P.lamp, L: '#64748b' }, 0, 14) +
  '<g class="pb-night"><rect x="-1" y="15" width="5" height="2" fill="#fde68a" opacity="0.25"/></g>'
const BUSH = sprite(['.GGG.', 'GGGGG', 'GGGGG'], { G: P.leaf }, 0, 21)
const DECOR: Array<[string, number]> = [[TREE, 9], [HOUSE, 12], [LAMP, 3], [BUSH, 5], [TREE, 9], [LAMP, 3], [BUSH, 5]]

/** Content drawn at the origin, moved to (x, 0). */
function at(x: number, content: string): string {
  return `<g transform="translate(${x} 0)">${content}</g>`
}


function skyline(x0: number, R: number): string {
  const bld = P.building
  const win = P.window
  const dim = P.dimWindow
  let s = ''
  const cbd = Math.min(R, 30)
  const blocks: Array<[number, number, number]> = [[0, 15, 3], [3, 18, 3], [10, 13, 3], [13, 17, 3]]
  for (let dx = 16, k = 0; dx + 2 <= cbd; k += 1) {
    const w = 2 + (k % 3)
    blocks.push([dx, 12 + ((k * 5) % 8), Math.min(w, cbd - dx)])
    dx += w + (k % 2)
  }
  for (const [dx, top, w] of blocks) {
    if (dx + w > R) continue
    s += rect(x0 + dx, top, w, 24 - top, dx % 2 ? P.buildingSide : bld)
    for (let y = top + 1; y < 23; y += 2) {
      for (let x = 0; x < w; x += 2) {
        const lit = (dx * 7 + y * 3 + x * 5) % 5
        if (lit === 0) s += rect(x0 + dx + x, y, 1, 1, win)
        else if (lit === 1) s += frames([rect(x0 + dx + x, y, 1, 1, win), rect(x0 + dx + x, y, 1, 1, dim)], 2 + (y % 5) * 0.7, x * 0.3)
      }
    }
  }
  if (R > cbd + 4) {
    const hx = x0 + cbd
    const hw = R - cbd
    if (hw >= 26) {
      // Rangitoto: a low, wide cone on the horizon
      const rx = hx + hw - 24
      for (let j = 0; j < 5; j += 1) s += rect(rx + 8 - 2 * j, 19 + j, 8 + 4 * j, 1, P.hill)
      s += rect(rx + 10, 18, 4, 1, P.hill)
    }
    s += rect(hx, 24, hw, 4, P.sea)
    for (let x = hx + 3; x < hx + hw - 3; x += 7) {
      s += frames([rect(x, 25 + (x % 2), 3, 1, P.wave), rect(x + 1, 26 - (x % 2), 3, 1, P.wave)], 1.4 + (x % 3) * 0.3)
    }
    for (let x = hx + 6; x + 6 < hx + hw; x += 18) {
      const boat = sprite(['..W...', '..WW..', '..WWW.', '..WWWW', 'HHHHHH', '.HHHH.'], { W: '#e5e7eb', H: '#7c4a2d' })
      s += path(boat, [[x, 18], [x, 19], [x, 19], [x, 18]], 2.2 + (x % 4) * 0.2)
    }
  }
  const t = x0 + Math.min(7, Math.max(2, R - 5))
  s += rect(t - 1, 21, 4, 3, '#7c849c') + rect(t, 9, 2, 15, P.tower) + rect(t - 1, 6, 4, 1, P.tower)
  s += rect(t - 2, 7, 6, 1, '#b8c0d4') + rect(t - 2, 8, 6, 1, win)
  s += rect(t - 1, 9, 4, 1, P.tower)
  s += rect(t, 3, 2, 3, P.tower) + rect(t + 1, 0, 1, 3, P.towerTop)
  s += frames([rect(t + 1, 0, 1, 1, C.red), rect(t + 1, 0, 1, 1, '#7f1d1d')], 1.2)
  return s
}

function garden(width: number): string {
  let s = ''
  let x = 5
  for (const [decoration, size] of DECOR) {
    if (x + size > width - 4) break
    s += at(x, decoration)
    x += size + 7
  }
  return s
}

// 每种状态只生成一次 SVG；分钟额度刷新复用同一 source，不重启动画。
// 画布由宿主 flex 容器居中裁边，角色保持 2 倍像素和原面板高度。
const scenes: Partial<Record<Mood, string>> = {}
export function sceneSvg(mood: Mood): string {
  if (scenes[mood]) return scenes[mood]!
  const left = (W - STAGE) / 2
  const draw = mood === 'waiting' ? scWaiting : mood === 'unknown' ? scUnknown
    : mood === 'working' ? scCode : mood === 'done' ? scParty : mood === 'relax' ? scIdle : scSleep
  const stage = `<defs><clipPath id="pb-stage"><rect width="${STAGE}" height="${H}"/></clipPath></defs>` +
    `<g transform="translate(${left} 0)"><g clip-path="url(#pb-stage)">${draw()}</g></g>`
  const body = backdrop(W) + garden(left) + skyline(left + STAGE, left) + stage
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" class="pb-scene" viewBox="0 0 ${W} ${H}" width="${SCENE_WIDTH}" height="${SCENE_HEIGHT}"` +
    ` shape-rendering="crispEdges" style="background:transparent;color-scheme:light dark">${THEME}${body}</svg>`
  scenes[mood] = svg
  return svg
}
