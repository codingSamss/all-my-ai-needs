// Pixel Buddy Quota Labels：由固定版本 BDF 提取的少量点阵字形，按 OFL-1.1 分发。
// 来源及全部上游许可见 quota-text-OFL.txt；运行时不安装、加载或下载字体。
// 每行首项为前进宽度，其后 12 项为位图行，最低位对应最左侧像素。
import { pixelMeterSvg, pixelPercentSvg } from './quota-pixels'

const GLYPHS: Record<string, readonly number[]> = {
  " ": [6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  "0": [6, 0, 0, 14, 17, 25, 21, 21, 19, 17, 14, 0, 0],
  "1": [6, 0, 0, 4, 7, 4, 4, 4, 4, 4, 31, 0, 0],
  "2": [6, 0, 0, 14, 17, 16, 8, 4, 2, 1, 31, 0, 0],
  "3": [6, 0, 0, 14, 17, 16, 12, 16, 16, 17, 14, 0, 0],
  "4": [6, 0, 0, 12, 10, 10, 9, 9, 31, 8, 8, 0, 0],
  "5": [6, 0, 0, 31, 1, 1, 15, 16, 16, 17, 14, 0, 0],
  "6": [6, 0, 0, 14, 17, 1, 15, 17, 17, 17, 14, 0, 0],
  "7": [6, 0, 0, 31, 16, 16, 8, 8, 4, 4, 4, 0, 0],
  "8": [6, 0, 0, 14, 17, 17, 14, 17, 17, 17, 14, 0, 0],
  "9": [6, 0, 0, 14, 17, 17, 17, 30, 16, 17, 14, 0, 0],
  "d": [6, 0, 0, 16, 16, 30, 17, 17, 17, 17, 30, 0, 0],
  "h": [6, 0, 0, 1, 1, 13, 19, 17, 17, 17, 17, 0, 0],
  "·": [12, 0, 0, 0, 0, 0, 0, 96, 96, 0, 0, 0, 0],
  "余": [12, 0, 112, 136, 260, 1787, 32, 32, 1022, 32, 292, 1571, 48],
  "分": [12, 0, 136, 136, 260, 260, 514, 1533, 272, 272, 264, 260, 195],
  "剩": [12, 0, 1072, 1294, 1288, 1407, 1322, 1387, 1322, 1387, 1052, 1066, 1865],
  "后": [12, 0, 960, 62, 2, 2, 2046, 2, 1018, 522, 522, 522, 1017],
  "天": [12, 0, 1022, 32, 32, 32, 2047, 32, 80, 80, 136, 260, 1539],
  "小": [12, 0, 32, 32, 32, 292, 548, 546, 1058, 1057, 32, 32, 56],
  "待": [12, 0, 132, 994, 129, 132, 2034, 515, 2034, 546, 578, 514, 898],
  "新": [12, 0, 1544, 447, 162, 148, 1983, 648, 703, 648, 682, 585, 588],
  "时": [12, 0, 512, 527, 2025, 521, 521, 559, 585, 585, 521, 527, 896],
  "更": [12, 0, 2047, 32, 1022, 546, 1022, 546, 1022, 34, 36, 24, 2023],
  "置": [12, 0, 2047, 1161, 2047, 32, 2047, 32, 508, 260, 508, 260, 2047],
  "重": [12, 0, 1022, 32, 2047, 546, 1022, 546, 1022, 32, 1022, 32, 2047],
  "间": [12, 0, 2041, 1026, 1024, 1273, 1161, 1161, 1273, 1161, 1161, 1273, 1537],
}

export type PixelLabel = { source: string; width: number; height: number }

export function pixelLabelSvg(text: string): PixelLabel | undefined {
  // 按原始 12px 点阵显示，保留清晰边缘并给方格条留出空间。
  const scale = 1
  let width = 0
  let path = ''
  if (!text || text.length > 32) return undefined
  for (const char of text) {
    const glyph = GLYPHS[char]
    // 字库外字符或异常长倒计时回退到宿主文字，不能显示缺字方框或裁掉信息。
    if (!glyph || (width + glyph[0]) * scale > 140) return undefined
    for (let y = 0; y < 12; y++) {
      let x = 0
      while (x < glyph[0]) {
        if (!(glyph[y + 1] & (1 << x))) { x++; continue }
        const start = x
        while (x < glyph[0] && (glyph[y + 1] & (1 << x))) x++
        path += `M${width + start} ${y}h${x - start}v1h-${x - start}z`
      }
    }
    width += glyph[0]
  }
  return {
    width: width * scale,
    height: 12 * scale,
    source: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} 12" width="${width * scale}" height="${12 * scale}" shape-rendering="crispEdges"><path fill="#8b8b85" d="${path}"/></svg>`,
  }
}

export function pixelQuotaCardSvg(title: string, remaining: number | undefined, caption: string, color: string): PixelLabel | undefined {
  const heading = pixelLabelSvg(title)
  const reset = pixelLabelSvg(caption)
  if (!heading || !reset || heading.width > 68) return undefined
  // 内部统一坐标排版，避免宿主把多个独立图片行紧贴，文字与方格条至少相隔 6px。
  return {
    width: 140,
    height: 52,
    source: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 52" width="140" height="52" shape-rendering="crispEdges">` +
      `<g transform="translate(0 2)">${heading.source}</g>` +
      `<g transform="translate(76 0)">${pixelPercentSvg(remaining, color)}</g>` +
      `<g transform="translate(0 22)">${pixelMeterSvg(remaining, color)}</g>` +
      `<g transform="translate(0 38)">${reset.source}</g></svg>`,
  }
}
