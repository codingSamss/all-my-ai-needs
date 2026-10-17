// SPDX-License-Identifier: MIT
// 角色与基础动作摘自 pixel-at-work，版权及固定提交见 scene-NOTICES.txt；固定房间、各状态道具、睡床与邮箱为本地绘制。
// 仅移植绘图；不引入工具分类、结果猜测、节日、轮询或上游事件钩子。
import type { CacheStage, Mood } from '../types'
export const DONE_SECONDS = 6.5
export const FLASH_SECONDS = 6
export const SCENE_WIDTH = 512
export const SCENE_HEIGHT = 54
const STAGE = 80
const W = SCENE_WIDTH / 2
const H = SCENE_HEIGHT / 2

// 角色自身的颜色不随主题变化，其余颜色一律走下面的 --v-* 变量。
const C = { o: '#d97757', ol: '#f2b49b', eye: '#2b1b17' }
const colors = {
  floor: 'var(--v-floor)', wood: 'var(--v-wood)', woodHi: 'var(--v-wood-light)', ink: 'var(--v-ink)',
  blue: 'var(--v-blue)', glass: 'var(--v-glass)', paper: 'var(--v-paper)', green: 'var(--v-green)',
  leaf: 'var(--v-leaf)', orange: 'var(--v-orange)', soft: 'var(--v-soft)', metal: 'var(--v-metal)',
  roof: 'var(--v-roof)', pink: 'var(--v-pink)', dim: 'var(--v-dim)', amber: 'var(--v-amber)',
  amberHi: 'var(--v-amber-hi)', red: 'var(--v-red)', gray: 'var(--v-gray)', screen: 'var(--v-screen)',
  night: 'var(--v-night)',
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

// 逐帧切换：首帧同时是不播放动画时的静态画面。
function frames(parts: string[], dur: number, begin = 0): string {
  return parts
    .map((p, i) => {
      const values = parts.map((_, j) => (j === i ? '1' : '0')).join(';')
      return `<g opacity="${i === 0 ? 1 : 0}"><animate attributeName="opacity" values="${values}" dur="${dur}s"` +
        ` begin="${-begin}s" calcMode="discrete" repeatCount="indefinite"/>${p}</g>`
    })
    .join('')
}

// 整像素平移；初始 transform 取第一个点，不播放动画时同样停在首帧位置。
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

function pulse(content: string, dur: number): string {
  return `<g><animate attributeName="opacity" values="1;0.35;1" dur="${dur}s" repeatCount="indefinite"/>${content}</g>`
}

// 配色随宿主主题变化；场景由当前状态生成，不读取时钟或添加轮询。
const THEME = `<style>
.pb-wait-static{display:none}
@media(prefers-reduced-motion:reduce){.pb-wait-motion{display:none}.pb-wait-static{display:inline}}
.pb-scene{--v-floor:#53534b;--v-wood:#836143;--v-wood-light:#ac855d;--v-ink:#798e91;--v-blue:#354955;--v-glass:#253844;--v-paper:#c3c3ad;--v-green:#437256;--v-leaf:#49644c;--v-orange:#b16a4d;--v-soft:#343a36;--v-metal:#6e7d80;--v-roof:#496164;--v-pink:#af7378;--v-dim:#747d79;--v-amber:#d4a23b;--v-amber-hi:#f0c765;--v-red:#c85a4f;--v-gray:#9aa3b5;--v-screen:#0b1020;--v-night:#141b24}
@media(prefers-color-scheme:light){
  .pb-scene{--v-floor:#c7c0b0;--v-wood:#a48059;--v-wood-light:#c3a47e;--v-ink:#718181;--v-blue:#9bc3cf;--v-glass:#c9e0e5;--v-paper:#f4efdf;--v-green:#679979;--v-leaf:#3f7d51;--v-orange:#ce8464;--v-soft:#dedad0;--v-metal:#9ba5a6;--v-roof:#809a9e;--v-pink:#d28a8b;--v-dim:#a1aaa6;--v-amber:#d4912a;--v-amber-hi:#f2b84c;--v-red:#d4574a;--v-gray:#8a93a0;--v-screen:#2b3445;--v-night:#44546b;--pb-press:#7c8d9d;--pb-press-hi:#a4b4c2;--pb-paper:#ffffff;--pb-paper-shade:#c4d1d9}
}
</style>`

// 小人只有两只小眼睛，表情全部由眼睛的位置和开合表达，不画嘴，也不画多余的手。
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
const LEGS = ['.O.O....O.O.', '.O.O....O.O.']
const BODY_PAL: Pal = { O: C.o, L: C.ol }

type Eyes = 'open' | 'blink' | 'shut' | 'think' | 'right' | 'rightBlink'

function eyes(x: number, y: number, kind: Eyes): string {
  const e = (dx: number, dy: number, w = 1, h = 2) => rect(x + dx, y + dy, w, h, C.eye)
  const open = e(3, 2) + e(8, 2), shut = e(2, 3, 2, 1) + e(8, 3, 2, 1), right = e(4, 2) + e(9, 2)
  const up = e(3, 1) + e(8, 1), upRight = e(4, 1) + e(9, 1), upLeft = e(2, 1) + e(7, 1)
  if (kind === 'shut') return shut
  if (kind === 'right') return right
  if (kind === 'blink') return frames([open, open, open, open, open, open, open, shut], 3.2)
  if (kind === 'rightBlink') return frames([right, right, right, right, right, right, right, shut], 5)
  if (kind === 'think') return frames([up, up, upRight, upRight, up, upLeft], 4.8)
  return open
}

const legs = (x: number, y: number) => sprite(LEGS, BODY_PAL, x, y + 8)
const body = (x: number, y: number) => sprite(BODY, BODY_PAL, x, y)
const critter = (x: number, y: number, kind: Eyes = 'blink') => legs(x, y) + body(x, y) + eyes(x, y, kind)
const hop = (content: string, dur: number) =>
  path(content, [[0, 0], [0, -2], [0, -3], [0, -2], [0, 0], [0, 0]], dur)

// ---- 各状态在 80×27 舞台内的画法，地面在 y=24 ----

// 思考：眼睛向上并在左中右之间慢慢转，头顶气泡里的省略号逐个出现。
function scThink(): string {
  let s = critter(22, 14, 'think')
  s += rect(35, 11, 2, 2, colors.paper) + rect(39, 8, 3, 3, colors.paper)
  s += rect(47, 0, 28, 1, colors.paper) + rect(46, 1, 30, 7, colors.paper) + rect(47, 8, 28, 1, colors.paper)
  const dot = (x: number) => rect(x, 3, 2, 2, colors.ink)
  return s + frames([dot(54), dot(54) + dot(60), dot(54) + dot(60) + dot(66), dot(54) + dot(60) + dot(66)], 2.4)
}

// 干活：敲键盘、屏幕里的代码行循环滚动；滚动只是循环动画，不代表进度。
function scWork(): string {
  let s = critter(12, 14)
  s += frames([rect(24, 18, 3, 1, C.o), rect(24, 19, 3, 1, C.o)], 0.3)
  s += rect(34, 5, 30, 15, colors.metal) + rect(35, 6, 28, 13, colors.screen) + rect(46, 20, 6, 2, colors.metal) + rect(42, 22, 14, 1, colors.dim)
  const palette = ['#c084fc', '#86efac', '#93c5fd', '#fca5a5', '#d1d5db', '#fde68a']
  const indents = [0, 2, 4, 4, 2, 4, 6, 0]
  const row = (i: number, r: number) => {
    const y = 8 + r * 2, indent = indents[i]
    return rect(37 + indent, y, 4 + ((i * 7) % 9), 1, palette[i % 6]) +
      rect(42 + indent + ((i * 7) % 9), y, 3 + ((i * 5) % 7), 1, palette[(i + 3) % 6])
  }
  const pages = Array.from({ length: 8 }, (_, f) => {
    let p = ''
    for (let r = 0; r < 5; r += 1) p += row((f + r) % 8, r)
    return p
  })
  return s + frames(pages, 2.4)
}

// 回复：对话气泡里的文字行逐行出现。
function scReply(): string {
  let s = critter(12, 14)
  s += rect(35, 1, 38, 1, colors.paper) + rect(34, 2, 40, 13, colors.paper) + rect(35, 15, 38, 1, colors.paper)
  s += rect(32, 11, 2, 1, colors.paper) + rect(30, 12, 2, 1, colors.paper) + rect(28, 13, 2, 1, colors.paper)
  const l1 = rect(38, 5, 26, 1, colors.ink), l2 = rect(38, 8, 30, 1, colors.ink), l3 = rect(38, 11, 18, 1, colors.ink)
  return s + frames([l1, l1 + l2, l1 + l2 + l3, l1 + l2 + l3], 3)
}

// 等你：原地小跳，旁边的牌子明暗交替；比完成时跳得快，也没有彩带。
function scAsk(): string {
  const s = hop(critter(24, 14), 0.7) + rect(56, 11, 2, 13, colors.wood)
  const bang = sprite(['.X.', '.X.', '.X.', '.X.', '...', '.X.'], { X: C.eye }, 56, 3)
  return s + frames([rect(46, 1, 22, 10, colors.amber) + bang, rect(46, 1, 22, 10, colors.amberHi) + bang], 0.6)
}

// 保留上游压纸机动作；颜色随现有主题切换，尺寸仍在原 80×27 舞台内。
function scCompact(): string {
  const cube = rect(0, 0, 6, 6, '#8b5cf6') + rect(0, 0, 6, 1, '#c4b5fd') +
    rect(1, 2, 4, 1, '#ddd6fe') + rect(1, 4, 3, 1, '#ddd6fe')
  const at = (x: number, y: number) => `<g transform="translate(${x} ${y})">${cube}</g>`
  const steel = 'var(--pb-press,#39404f)', steelHi = 'var(--pb-press-hi,#59617a)'
  let s = critter(3, 14)
  s += rect(18, 2, 2, 22, steel) + rect(40, 2, 2, 22, steel) + rect(18, 2, 24, 2, steelHi)
  const phase = (plate: number, top: number, x: number) => {
    let p = rect(29, 4, 2, plate - 4, colors.gray) + rect(21, plate, 18, 2, steelHi)
    if (top > 0) for (let y = top; y < 24; y += 2) p += rect(22, y, 16, 1, 'var(--pb-paper,#f7f3e8)') + rect(22, y + 1, 16, 1, 'var(--pb-paper-shade,#c8bfa9)')
    if (x > 0) p += at(x, 18)
    return p
  }
  s += frames([phase(5, 10, 0), phase(9, 13, 0), phase(13, 16, 0), phase(17, 20, 0), phase(5, 0, 27), phase(5, 0, 48)], 3)
  return s + at(60, 18) + at(66, 18) + at(63, 12)
}

function scWaiting(): string {
  // 邮箱始终为空；旗帜和信封图案是固定标识，不能用循环动画暗示收到结果或完成进度。
  let mailbox = rect(54, 16, 3, 8, colors.wood) + rect(54, 16, 1, 8, colors.woodHi)
  mailbox += rect(46, 5, 16, 1, colors.roof) + rect(44, 6, 20, 2, colors.roof) +
    rect(43, 8, 22, 8, colors.roof) + rect(50, 8, 15, 8, colors.ink)
  mailbox += rect(45, 7, 3, 1, colors.ink) + rect(44, 8, 5, 7, '#283e3e') +
    rect(43, 15, 7, 1, colors.metal) + rect(39, 16, 6, 1, colors.roof) + rect(38, 17, 5, 1, colors.ink)
  mailbox += rect(59, 1, 1, 5, '#c94f40') + rect(60, 1, 5, 3, '#c94f40')
  mailbox += sprite(['IPPPPPPPI', 'PIPPPPPIP', 'PPIPPPIPP', 'PPPIPIPPP', 'PPPPIPPPP', 'PPPPPPPPP'],
    { P: colors.paper, I: colors.wood }, 53, 9)

  // 脚掌固定落地，身体只挪 1–2 个逻辑像素；整像素分帧保持轮廓清晰，不连续旋转或缩放。
  const pose = (dx = 0, lift = 0, blink = false, look = 0) => {
    const x = 28 + dx, y = 14 - lift
    let s = sprite(BODY, BODY_PAL, x, y)
    for (const foot of [29, 31, 36, 38]) {
      s += rect(Math.min(foot, foot + dx), 22 - lift, 1 + Math.abs(dx), 1, C.o) +
        rect(foot, 23 - lift, 1, 1 + lift, C.o)
    }
    s += blink ? rect(x + 2, y + 3, 2, 1, C.eye) + rect(x + 8, y + 3, 2, 1, C.eye)
      : rect(x + 3 + look, y + 2, 1, 2, C.eye) + rect(x + 8 + look, y + 2, 1, 2, C.eye)
    return s
  }
  const poses = [pose(), pose(1, 1, false, 1), pose(2, 2, false, 1), pose(0, 0, true), pose(-1), pose(1)]
  // 8 秒内只做一轮小动作，尾段安静等候；用 SVG 自身时序，不增加插件计时器或状态更新。
  const beats = [[0, 0], [1.2, 1], [1.45, 2], [2.05, 1], [2.3, 0], [2.55, 3], [2.75, 0],
    [3.3, 4], [3.7, 0], [4.1, 5], [4.5, 0], [4.9, 4], [5.3, 0], [5.5, 3], [5.7, 0], [8, 0]]
  const keyTimes = beats.map(([time]) => time / 8).join(';')
  const motion = poses.map((drawing, i) => `<g opacity="${i === 0 ? 1 : 0}"><animate attributeName="opacity"` +
    ` values="${beats.map(([, frame]) => frame === i ? 1 : 0).join(';')}" keyTimes="${keyTimes}"` +
    ` dur="8s" calcMode="discrete" repeatCount="indefinite"/>${drawing}</g>`).join('')
  return mailbox + `<g class="pb-wait-motion">${motion}</g><g class="pb-wait-static">${poses[0]}</g>`
}

// 未知：小人静静看向一个问号，整幅画面没有任何动画，不暗示任务仍在执行。
function scUnknown(): string {
  return critter(24, 14, 'right') + rect(37, 11, 2, 2, colors.gray) + rect(41, 8, 2, 2, colors.gray) +
    sprite(['.QQQ.', 'Q...Q', '....Q', '...Q.', '..Q..', '.....', '..Q..'], { Q: colors.gray }, 46, 1)
}

function scParty(): string {
  let s = hop(critter(34, 14), 0.9)
  const confetti = ['#f472b6', '#60a5fa', '#fbbf24', '#4ade80', '#a78bfa', '#f87171']
  for (let i = 0; i < 20; i += 1) {
    const x = 3 + ((i * 37) % 75)
    const c = confetti[i % confetti.length]
    const dur = 1.6 + ((i * 7) % 5) * 0.25
    s += path(frames([rect(0, 0, 1, 2, c), rect(0, 0, 2, 1, c)], 0.3), line(x, -2, x + ((i % 3) - 1) * 3, 23, 12), dur, (i * 0.37) % dur)
  }
  return s
}

// 没有嘴和手：热咖啡时身子凑向杯子并闭眼，算一口；温时间隔更久；凉了只盯着杯子。
function scRest(cache: CacheStage): string {
  const x = 26, y = 14
  let s = legs(x, y)
  const plain = body(x, y), open = eyes(x, y, 'open'), shut = eyes(x, y, 'shut')
  if (cache === 'hot') {
    s += path(plain + frames([open, open, open, open, shut, shut, open, open], 6),
      [[0, 0], [0, 0], [0, 0], [1, 0], [2, 0], [2, 0], [1, 0], [0, 0]], 6)
  } else if (cache === 'warm') {
    const lean = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 1, 0, 0, 0]
    s += path(plain + frames(lean.map((_, i) => i === 10 || i === 11 ? shut : open), 12),
      lean.map((v): [number, number] => [v, 0]), 12)
  } else {
    s += plain + eyes(x, y, 'rightBlink')
  }
  s += rect(40, 18, 24, 2, colors.wood) + rect(42, 20, 1, 4, colors.wood) + rect(61, 20, 1, 4, colors.wood)
  const cup = cache === 'cold' ? colors.blue : colors.paper
  s += rect(43, 12, 6, 6, cup) + rect(49, 13, 2, 1, cup) + rect(50, 14, 1, 2, cup) + rect(49, 16, 2, 1, cup)
  s += rect(44, 12, 4, 1, cache === 'cold' ? colors.dim : '#7c4a2d')
  if (cache === 'hot') {
    const steam = (o: number) => rect(44 + o, 9, 1, 2, colors.gray) + rect(45 - o, 6, 1, 2, colors.gray) + rect(46 + o, 3, 1, 2, colors.gray)
    s += frames([steam(0), steam(1)], 1)
  } else if (cache === 'warm') {
    s += frames([rect(45, 9, 1, 2, colors.gray) + rect(46, 6, 1, 2, colors.gray), ''], 2.4)
  } else {
    s += sprite(['.X.', 'XXX', '.X.'], { X: colors.glass }, 53, 7) + rect(45, 9, 1, 1, colors.glass)
  }
  return s
}

// 空闲小屋盖上毯子；与短暂休息的咖啡桌区分，阶段计时仍由现有入口负责。
function scSleep(): string {
  let s = rect(24, 21, 41, 3, colors.wood) + rect(23, 18, 2, 6, colors.woodHi) +
    rect(64, 17, 2, 7, colors.woodHi) + rect(26, 19, 35, 2, colors.paper)
  s += critter(30, 12, 'shut') + rect(29, 19, 20, 3, colors.blue) + rect(29, 19, 20, 1, colors.glass)
  const z = sprite(['ZZZZ', '..Z.', '.Z..', 'ZZZZ'], { Z: colors.ink })
  for (let i = 0; i < 2; i += 1) s += path(z, line(45, 11, 53, 1, 6), 3, i * 1.5)
  return s
}

// 出错：头顶冒烟、贴创可贴、身子发抖，红色感叹号闪烁；只表示这一轮没成功，不猜原因。
function scError(): string {
  const hurt = critter(26, 14, 'open') + rect(33, 14, 3, 2, colors.paper) + rect(34, 14, 1, 2, colors.red)
  let s = path(hurt, [[0, 0], [1, 0], [0, 0], [-1, 0]], 0.4)
  const puff = sprite(['.X.', 'XXX'], { X: colors.gray })
  for (let i = 0; i < 2; i += 1) s += path(puff, line(30, 12, 34, 0, 6), 2.4, i * 1.2)
  return s + frames([sprite(['X', 'X', 'X', '.', 'X'], { X: colors.red }, 46, 6), ''], 1.2)
}

// 中断：小人停住不眨眼，旁边的暂停符号缓慢明暗。
function scAbort(): string {
  return critter(24, 14, 'open') + pulse(rect(46, 5, 4, 12, colors.amber) + rect(53, 5, 4, 12, colors.amber), 2.4)
}

// ---- 固定房间：所有状态共用，只有睡觉时换成夜晚 ----
// 大面积留白保持透明，直接透出宿主面板；不能按主题猜一个近似底色，否则会形成色差框。
function pot(x: number, y = 17): string {
  return rect(x + 2, y + 5, 5, 3, colors.wood) + rect(x + 3, y + 2, 1, 4, colors.leaf) +
    rect(x, y + 1, 4, 3, colors.leaf) + rect(x + 4, y, 4, 3, colors.green)
}

function shelf(x: number): string {
  let s = rect(x, 3, 30, 21, colors.wood) + rect(x + 2, 4, 26, 19, colors.soft)
  for (let j = 0; j < 2; j += 1) {
    for (let i = 0; i < 7; i += 1) s += rect(x + 3 + i * 3, 5 + j * 9 + i % 3, 2, 7 - i % 3,
      [colors.blue, colors.orange, colors.paper, colors.green][i % 4])
    s += rect(x + 1, 12 + j * 9, 28, 1, colors.woodHi)
  }
  return s
}

// 22×14 的窗：白天是淡色玻璃和一朵云，睡觉时换成夜空、月牙与星点。
function windowView(x: number, y: number, night: boolean): string {
  let s = rect(x, y, 22, 14, colors.wood) + rect(x + 1, y + 1, 20, 12, night ? colors.night : colors.glass)
  s += night
    ? sprite(['.M.', 'MM.', 'MM.', '.M.'], { M: '#e9e2c6' }, x + 14, y + 2) +
      rect(x + 4, y + 3, 1, 1, '#cfd6e6') + rect(x + 7, y + 9, 1, 1, '#cfd6e6') + rect(x + 17, y + 9, 1, 1, '#cfd6e6')
    : rect(x + 4, y + 4, 6, 1, colors.paper) + rect(x + 5, y + 3, 3, 1, colors.paper)
  return s + rect(x + 10, y + 1, 2, 12, colors.woodHi) + rect(x + 1, y + 6, 20, 1, colors.woodHi)
}

// 软木板上只有固定的便签和图钉，不显示任何真实任务内容。
function pinboard(x: number): string {
  let s = rect(x, 4, 26, 16, colors.wood) + rect(x + 1, 5, 24, 14, colors.woodHi)
  s += rect(x + 3, 7, 6, 5, colors.paper) + rect(x + 4, 9, 4, 1, colors.ink) + rect(x + 4, 11, 3, 1, colors.ink)
  s += rect(x + 11, 7, 5, 4, colors.amber) + rect(x + 12, 9, 3, 1, colors.paper)
  s += rect(x + 18, 8, 5, 5, colors.blue) + rect(x + 19, 10, 3, 1, colors.paper)
  s += rect(x + 4, 14, 6, 4, colors.pink) + rect(x + 13, 14, 9, 4, colors.paper) + rect(x + 14, 16, 7, 1, colors.ink)
  for (const [px, py] of [[5, 7], [13, 7], [20, 8], [6, 14], [16, 14]]) s += rect(x + px, py, 1, 1, colors.red)
  return s
}

function picture(x: number): string {
  return rect(x, 5, 14, 11, colors.wood) + rect(x + 1, 6, 12, 9, colors.glass) +
    rect(x + 1, 12, 12, 3, colors.leaf) + rect(x + 4, 10, 5, 2, colors.green) + rect(x + 9, 7, 2, 2, colors.amberHi)
}

function cabinet(x: number): string {
  let s = rect(x, 15, 20, 9, colors.wood) + rect(x - 1, 14, 22, 2, colors.woodHi)
  s += rect(x + 2, 17, 7, 6, colors.soft) + rect(x + 11, 17, 7, 6, colors.soft)
  s += rect(x + 8, 19, 1, 2, colors.woodHi) + rect(x + 11, 19, 1, 2, colors.woodHi)
  return s + pot(x + 2, 6) + rect(x + 12, 13, 7, 1, colors.orange) + rect(x + 12, 11, 7, 2, colors.blue)
}

// 落地灯白天亮着，睡觉时熄灭。
function lamp(x: number, night: boolean): string {
  let s = sprite(['..SSS..', '.SSSSS.', 'SSSSSSS'], { S: night ? colors.dim : colors.paper }, x, 8)
  if (!night) s += rect(x + 1, 10, 5, 1, colors.amberHi)
  return s + rect(x + 3, 11, 1, 12, colors.ink) + rect(x + 1, 23, 5, 1, colors.ink)
}

function room(night: boolean): string {
  let s = rect(0, 24, 256, 3, colors.floor) + rect(0, 24, 256, 1, colors.woodHi)
  s += shelf(6)
  s += rect(41, 3, 30, 1, colors.woodHi) + rect(40, 3, 1, 2, colors.wood) + rect(71, 3, 1, 2, colors.wood)
  s += windowView(45, 5, night)
  for (const x of [42, 66]) {
    s += rect(x, 4, 4, 16, colors.pink) + rect(x + (x < 50 ? 2 : 1), 5, 1, 14, colors.orange) + rect(x, 12, 4, 1, colors.woodHi)
  }
  s += rect(43, 19, 26, 1, colors.woodHi) + rect(44, 20, 24, 1, colors.wood)
  s += pot(74, 16)
  s += rect(94, 25, 68, 1, colors.pink) + rect(96, 26, 64, 1, colors.orange) + rect(92, 25, 2, 1, colors.paper) + rect(162, 25, 2, 1, colors.paper)
  return s + lamp(174, night) + pinboard(188) + picture(218) + cabinet(234)
}

const draw: Record<Mood, (cache: CacheStage) => string> = {
  idle: scSleep, working: scWork, thinking: scThink, replying: scReply, asking: scAsk, waiting: scWaiting,
  compact: scCompact, unknown: scUnknown, done: scParty, relax: scRest, error: scError, aborted: scAbort,
}

// 每种状态只生成一次 SVG；分钟额度刷新复用同一 source，不重启动画。咖啡杯随缓存温度分三种画法。
// 画布由宿主 flex 容器居中裁边，角色保持 2 倍像素和原面板高度。
const scenes = new Map<string, string>()
export function sceneSvg(mood: Mood, cache: CacheStage = 'hot'): string {
  const key = mood === 'relax' ? `${mood}:${cache}` : mood
  const cached = scenes.get(key)
  if (cached) return cached
  const left = (W - STAGE) / 2
  const stage = `<defs><clipPath id="pb-stage"><rect width="${STAGE}" height="${H}"/></clipPath></defs>` +
    `<g transform="translate(${left} 0)"><g clip-path="url(#pb-stage)">${(draw[mood] ?? scUnknown)(cache)}</g></g>`
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" class="pb-scene" viewBox="0 0 ${W} ${H}" width="${SCENE_WIDTH}" height="${SCENE_HEIGHT}"` +
    ` shape-rendering="crispEdges" style="background:transparent;color-scheme:light dark">${THEME}${room(mood === 'idle')}${stage}</svg>`
  scenes.set(key, svg)
  return svg
}
