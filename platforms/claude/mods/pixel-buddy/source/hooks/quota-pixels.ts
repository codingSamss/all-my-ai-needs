// 静态字形与图标来源、提交和许可见 pixel-quota-NOTICES.txt；不加载外部字体。
const GLYPHS: Record<string, readonly number[]> = {
  "0": [62, 99, 115, 123, 111, 103, 62, 0],
  "1": [12, 14, 12, 12, 12, 12, 63, 0],
  "2": [30, 51, 48, 28, 6, 51, 63, 0],
  "3": [30, 51, 48, 28, 48, 51, 30, 0],
  "4": [56, 60, 54, 51, 127, 48, 120, 0],
  "5": [63, 3, 31, 48, 48, 51, 30, 0],
  "6": [28, 6, 3, 31, 51, 51, 30, 0],
  "7": [63, 51, 48, 24, 12, 12, 12, 0],
  "8": [30, 51, 51, 30, 51, 51, 30, 0],
  "9": [30, 51, 51, 62, 48, 24, 14, 0],
  "%": [0, 99, 51, 24, 12, 102, 99, 0],
  "-": [0, 0, 0, 63, 0, 0, 0, 0],
}

const ICONS = {
  "clock": "M6 2h12v2H6zM2 6h2v12H2zm18 0h2v12h-2zm-2-2h2v2h-2zM4 4h2v2H4zm2 18h12v-2H6zm12-2h2v-2h-2zM4 20h2v-2H4zm7-14h2v7h-2zm2 7h2v2h-2zm2 2h2v2h-2z",
  "calendar": "M5 4h14v2H5zm0 16h14v2H5zM3 10h2v10H3zm0-4h2v2H3zm16 0h2v2h-2zm0 4h2v10h-2zM3 8h18v2H3zm12-6h2v2h-2zM7 2h2v2H7z"
} as const

export const PIXEL_PERCENT_WIDTH = 64
export const PIXEL_PERCENT_HEIGHT = 16
export const PIXEL_METER_WIDTH = 112
export const PIXEL_METER_HEIGHT = 10

// SDK 读数可能暂缺；限制到有效范围后再画图，未知不能伪装成满额。
const bounded = (remaining: number | undefined) =>
  typeof remaining === 'number' && Number.isFinite(remaining)
    ? Math.min(100, Math.max(0, remaining)) : undefined
const safeInk = (color: string) => /^#[0-9a-f]{6}$/i.test(color) ? color : '#9a9a9a'

export function pixelIconSvg(kind: 'clock' | 'cal'): string {
  const path = kind === 'clock' ? ICONS.clock : ICONS.calendar
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" shape-rendering="crispEdges"><path fill="#9a9a9a" d="${path}"/></svg>`
}

export function pixelPercentSvg(remaining: number | undefined, color: string): string {
  const value = bounded(remaining)
  const ink = safeInk(color)
  const label = value === undefined ? '--%' : `${Math.round(value)}%`
  // 固定四字宽并靠右，100% 与个位数之间切换不会推移旁边的文字。
  const offset = (4 - label.length) * 8
  let pixels = ''
  for (let index = 0; index < label.length; index++) {
    const rows = GLYPHS[label[index]]
    for (let y = 0; y < 8; y++) {
      for (let x = 0; x < 8; x++) {
        if (rows[y] & (1 << x)) pixels += `<rect x="${offset + index * 8 + x}" y="${y}" width="1" height="1" fill="${ink}"/>`
      }
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 8" width="${PIXEL_PERCENT_WIDTH}" height="${PIXEL_PERCENT_HEIGHT}" shape-rendering="crispEdges">${pixels}</svg>`
}

export function pixelMeterSvg(remaining: number | undefined, color: string): string {
  const value = bounded(remaining)
  const ink = safeInk(color)
  let pixels = ''
  for (let index = 0; index < 10; index++) {
    const x = 1 + index * 11
    pixels += `<rect x="${x}" y="0" width="8" height="10" fill="#9a9a9a" fill-opacity="0.25"/>`
    // 每格为 10%，仅向下取整到 1.25% 像素刻度；99% 不画成全满，读数仍显示整数。
    const width = value === undefined ? 0 : Math.floor(Math.min(1, Math.max(0, value / 10 - index)) * 8 + 1e-9)
    if (width) pixels += `<rect x="${x}" y="0" width="${width}" height="10" fill="${ink}"/>`
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 112 10" width="${PIXEL_METER_WIDTH}" height="${PIXEL_METER_HEIGHT}" shape-rendering="crispEdges">${pixels}</svg>`
}
