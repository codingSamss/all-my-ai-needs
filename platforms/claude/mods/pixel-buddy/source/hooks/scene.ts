// SPDX-License-Identifier: MIT
// 角色与基础动作摘自 pixel-at-work，版权及固定提交见 scene-NOTICES.txt；七景背景、睡床与沙漏为本地绘制。
// 仅移植绘图；不引入工具分类、结果猜测、节日、轮询或上游事件钩子。
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


// 配色随宿主主题变化；七景背景由当前状态生成，不读取时钟或添加轮询。
const THEME = `<style>
.pb-wait-static{display:none}
@media(prefers-reduced-motion:reduce){.pb-wait-motion{display:none}.pb-wait-static{display:inline}}
.pb-scene{--v-wall:#303331;--v-floor:#53534b;--v-wood:#836143;--v-wood-light:#ac855d;--v-ink:#798e91;--v-blue:#354955;--v-glass:#253844;--v-paper:#c3c3ad;--v-green:#437256;--v-leaf:#49644c;--v-orange:#b16a4d;--v-soft:#343a36;--v-metal:#6e7d80;--v-roof:#496164;--v-cozy:#353331;--v-pink:#af7378;--v-dim:#747d79}
@media(prefers-color-scheme:light){
  .pb-scene{--v-wall:#e6e1d6;--v-floor:#c7c0b0;--v-wood:#a48059;--v-wood-light:#c3a47e;--v-ink:#718181;--v-blue:#9bc3cf;--v-glass:#c9e0e5;--v-paper:#f4efdf;--v-green:#679979;--v-leaf:#3f7d51;--v-orange:#ce8464;--v-soft:#dedad0;--v-metal:#9ba5a6;--v-roof:#809a9e;--v-cozy:#ebe0cb;--v-pink:#d28a8b;--v-dim:#a1aaa6;--pb-press:#7c8d9d;--pb-press-hi:#a4b4c2;--pb-paper:#ffffff;--pb-paper-shade:#c4d1d9}
}
</style>`

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

// 保留上游压纸机动作；颜色随现有主题切换，尺寸仍在原 80×27 舞台内。
function scCompact(): string {
  const cube = rect(0, 0, 6, 6, '#8b5cf6') + rect(0, 0, 6, 1, '#c4b5fd') +
    rect(1, 2, 4, 1, '#ddd6fe') + rect(1, 4, 3, 1, '#ddd6fe')
  const at = (x: number, y: number) => `<g transform="translate(${x} ${y})">${cube}</g>`
  const steel = 'var(--pb-press,#39404f)', steelHi = 'var(--pb-press-hi,#59617a)'
  let s = critter(3, 14)
  s += rect(18, 2, 2, 22, steel) + rect(40, 2, 2, 22, steel) + rect(18, 2, 24, 2, steelHi)
  const phase = (plate: number, top: number, x: number) => {
    let p = rect(29, 4, 2, plate - 4, C.gray) + rect(21, plate, 18, 2, steelHi)
    if (top > 0) for (let y = top; y < 24; y += 2) p += rect(22, y, 16, 1, 'var(--pb-paper,#f7f3e8)') + rect(22, y + 1, 16, 1, 'var(--pb-paper-shade,#c8bfa9)')
    if (x > 0) p += at(x, 18)
    return p
  }
  s += frames([phase(5, 10, 0), phase(9, 13, 0), phase(13, 16, 0), phase(17, 20, 0), phase(5, 0, 27), phase(5, 0, 48)], 3)
  return s + at(60, 18) + at(66, 18) + at(63, 12)
}


// 空闲小屋盖上毯子；与短暂休息的咖啡桌区分，阶段计时仍由现有入口负责。
function scSleep(): string {
  let s = rect(24, 21, 41, 3, colors.wood) + rect(23, 18, 2, 6, colors.woodHi) +
    rect(64, 17, 2, 7, colors.woodHi) + rect(26, 19, 35, 2, colors.paper)
  s += critter(30, 12, 'asleep') + rect(29, 19, 20, 3, colors.blue) + rect(29, 19, 20, 1, colors.glass)
  const z = sprite(['ZZZZ', '..Z.', '.Z..', 'ZZZZ'], { Z: colors.ink })
  for (let i = 0; i < 2; i += 1) s += path(z, line(45, 11, 53, 1, 6), 3, i * 1.5)
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

// 七个地点沿用已确认的 256×27 像素草图；只在压缩工坊增加局部传送带运动。
const colors = {
  wall: 'var(--v-wall)', floor: 'var(--v-floor)', wood: 'var(--v-wood)', woodHi: 'var(--v-wood-light)',
  ink: 'var(--v-ink)', blue: 'var(--v-blue)', glass: 'var(--v-glass)', paper: 'var(--v-paper)',
  green: 'var(--v-green)', leaf: 'var(--v-leaf)', orange: 'var(--v-orange)', soft: 'var(--v-soft)',
  metal: 'var(--v-metal)', roof: 'var(--v-roof)', cozy: 'var(--v-cozy)', pink: 'var(--v-pink)', dim: 'var(--v-dim)',
}
const r = rect
const base = (color = colors.floor): string => r(0, 24, 256, 3, color) + r(0, 24, 256, 1, colors.woodHi)

function pot(x: number, y = 17): string {
  return r(x + 2, y + 5, 5, 3, colors.wood) + r(x + 3, y + 2, 1, 4, colors.leaf) +
    r(x, y + 1, 4, 3, colors.leaf) + r(x + 4, y, 4, 3, colors.green)
}

function windowPane(x: number, y: number, w = 25, h = 14): string {
  return r(x, y, w, h, colors.wood) + r(x + 1, y + 1, w - 2, h - 2, colors.glass) +
    r(x + Math.floor(w / 2), y + 1, 1, h - 2, colors.woodHi) + r(x + 1, y + Math.floor(h / 2), w - 2, 1, colors.woodHi)
}

function bench(x: number, y: number, w = 25): string {
  return r(x, y, w, 2, colors.woodHi) + r(x + 2, y + 3, w - 4, 2, colors.wood) +
    r(x + 3, y + 5, 2, 4, colors.ink) + r(x + w - 5, y + 5, 2, 4, colors.ink)
}

function crate(x: number, y: number, color = colors.wood): string {
  return r(x, y, 10, 8, color) + r(x + 1, y + 1, 8, 1, colors.woodHi) +
    r(x + 1, y + 5, 8, 1, colors.woodHi) + r(x + 4, y, 2, 8, colors.woodHi)
}

function shelf(x: number): string {
  let s = r(x, 3, 30, 21, colors.wood) + r(x + 2, 4, 26, 19, colors.soft)
  for (let j = 0; j < 2; j += 1) {
    for (let i = 0; i < 7; i += 1) s += r(x + 3 + i * 3, 5 + j * 9 + i % 3, 2, 7 - i % 3,
      [colors.blue, colors.orange, colors.paper, colors.green][i % 4])
    s += r(x + 1, 12 + j * 9, 28, 1, colors.woodHi)
  }
  return s
}

// 大面积留白保持透明，直接透出宿主面板；不能按主题猜一个近似底色，否则会形成色差框。
function locationBackdrop(mood: Mood): string {
  let s='';
  if(mood==='working'){
    s=base()+shelf(8)+shelf(209)+windowPane(48,4,30,15);
    s+=r(41,21,40,2,colors.woodHi)+r(44,23,2,1,colors.wood)+pot(69,13);
    s+=r(174,7,23,12,colors.paper)+r(177,10,8,1,colors.blue)+r(177,13,15,1,colors.green)+r(177,16,11,1,colors.orange);
    s+=r(115,0,1,2,colors.ink)+r(111,2,9,1,colors.wood)+r(112,3,7,1,colors.paper);
  }else if(mood==='waiting'){
    s=r(0,21,256,3,colors.soft)+base(colors.metal);
    s+=r(7,2,241,2,colors.roof)+r(12,4,231,1,colors.ink);
    for(const x of [12,76,179,242])s+=r(x,5,2,19,colors.roof);
    s+=bench(31,15,33)+bench(191,15,33);
    s+=r(86,6,23,3,colors.paper)+r(88,7,9,1,colors.ink)+r(100,7,6,1,colors.orange);
    s+=sprite(['..CCC..','.CC.CC.','CC...CC','CC.C.CC','CC.CCCC','.CC.CC.','..CCC..'],{C:colors.ink},157,5);
    for(let x=0;x<256;x+=8)s+=r(x,25,4,1,colors.paper);
    s+=r(229,18,5,6,colors.wood)+r(230,16,3,1,colors.ink)+r(229,17,1,2,colors.ink)+r(233,17,1,2,colors.ink);
  }else if(mood==='compact'){
    s=base(colors.metal);
    for(const x of [10,79,176,245])s+=r(x,0,2,24,colors.metal);
    s+=r(0,4,256,2,colors.ink)+r(0,6,256,1,colors.metal);
    s+=r(4,22,78,2,colors.ink)+r(171,22,79,2,colors.ink);
    // 两侧传送带共用一组两帧动画，减少同步运动的 SMIL 节点数。
    const belt = ['', ''];
    for(let x=8;x<250;x+=8)if(x<80||x>174){belt[0]+=r(x,22,3,1,colors.paper);belt[1]+=r(x+2,22,3,1,colors.paper)}
    s+=frames(belt,1.6);
    for(let i=0;i<4;i++)s+=r(18+i*12,16-(i%2)*2,9,5+(i%2)*2,colors.paper)+r(18+i*12,18,9,1,colors.metal);
    s+=crate(188,14)+crate(199,14)+crate(194,6)+crate(222,14);
    s+=r(223,7,9,4,colors.orange)+r(225,8,5,1,colors.paper);
  }else if(mood==='done'){
    s=base(colors.soft);
    for(let x=6;x<250;x+=15){const y=2+Math.floor(Math.abs(128-x)/50);s+=r(x,y,15,1,colors.wood);s+=sprite(['FFFFF','.FFF.','..F..'],{F:[colors.orange,colors.blue,colors.green,colors.pink][Math.floor(x/15)%4]},x+4,y+1)}
    s+=r(87,23,81,1,colors.paper)+r(83,24,89,2,colors.woodHi)+r(78,26,99,1,colors.wood);
    for(const x of [22,218]){s+=pot(x,16)+r(x+7,4,1,13,colors.wood);s+=sprite(['.BBBB.','BBBBBB','BBBBBB','.BBBB.','..BB..'],{B:x===22?colors.pink:colors.blue},x+5,1)}
    for(const x of [48,186])s+=r(x,19,14,5,colors.wood)+r(x-1,17,16,3,colors.green)+r(x+3,15,8,2,colors.leaf);
  }else if(mood==='relax'){
    s=base(colors.woodHi);
    s+=r(9,1,237,2,colors.wood);
    for(let x=10;x<246;x+=8)s+=r(x,3,8,4,(Math.floor((x-10)/8)%2)?colors.paper:colors.green)+r(x,7,7,1,(Math.floor((x-10)/8)%2)?colors.paper:colors.green);
    s+=r(13,8,2,16,colors.wood)+r(241,8,2,16,colors.wood)+windowPane(25,10,28,12);
    s+=r(65,11,16,13,colors.wood)+r(67,13,12,8,colors.soft)+r(70,15,7,1,colors.paper)+r(70,18,5,1,colors.paper);
    s+=r(180,18,22,2,colors.wood)+r(190,20,2,4,colors.wood)+r(185,14,5,4,colors.paper)+bench(207,16,21)+pot(224,16);
    for(let x=0;x<256;x+=16)s+=r(x,26,7,1,colors.floor);
  }else if(mood==='idle'){
    s=base(colors.wood);
    for(let x=0;x<256;x+=16)s+=r(x,0,1,24,colors.soft);
    s+=r(0,0,256,2,colors.woodHi)+windowPane(28,5,32,15);
    s+=r(25,4,3,19,colors.orange)+r(60,4,3,19,colors.orange)+r(20,23,50,1,colors.woodHi);
    s+=r(179,19,23,2,colors.wood)+r(182,21,2,3,colors.wood)+r(197,21,2,3,colors.wood)+r(190,14,1,5,colors.ink)+r(185,11,11,3,colors.paper);
    s+=r(216,10,20,14,colors.metal)+r(214,9,24,2,colors.ink)+r(221,15,10,8,colors.wood)+r(219,23,14,1,colors.ink);
    s+=r(140,2,12,5,colors.wood)+r(141,3,10,3,colors.paper);
  }else{
    s=base(colors.metal);
    s+=r(20,7,37,15,colors.metal)+r(22,9,33,11,colors.paper)+r(26,12,10,1,colors.dim)+r(35,12,1,5,colors.dim)+r(35,16,13,1,colors.dim)+r(27,22,2,2,colors.metal)+r(49,22,2,2,colors.metal);
    s+=r(88,4,78,2,colors.roof)+r(92,6,2,18,colors.metal)+r(161,6,2,18,colors.metal);
    s+=r(191,10,32,2,colors.metal)+r(193,12,2,12,colors.metal)+r(219,12,2,12,colors.metal)+r(198,15,17,6,colors.paper)+r(201,17,11,1,colors.dim);
    s+=pot(70,16)+pot(234,16);
  }
  return s;
}

// 每种状态只生成一次 SVG；分钟额度刷新复用同一 source，不重启动画。
// 画布由宿主 flex 容器居中裁边，角色保持 2 倍像素和原面板高度。
const scenes: Partial<Record<Mood, string>> = {}
export function sceneSvg(mood: Mood): string {
  if (scenes[mood]) return scenes[mood]!
  const left = (W - STAGE) / 2
  const draw = mood === 'compact' ? scCompact : mood === 'waiting' ? scWaiting : mood === 'unknown' ? scUnknown : mood === 'working' ? scCode : mood === 'done' ? scParty : mood === 'relax' ? scIdle : scSleep
  const stage = `<defs><clipPath id="pb-stage"><rect width="${STAGE}" height="${H}"/></clipPath></defs>` +
    `<g transform="translate(${left} 0)"><g clip-path="url(#pb-stage)">${draw()}</g></g>`
  const body = locationBackdrop(mood) + stage
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" class="pb-scene" viewBox="0 0 ${W} ${H}" width="${SCENE_WIDTH}" height="${SCENE_HEIGHT}"` +
    ` shape-rendering="crispEdges" style="background:transparent;color-scheme:light dark">${THEME}${body}</svg>`
  scenes[mood] = svg
  return svg
}
