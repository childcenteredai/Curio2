/**
 * Direct-instruction explanation screen: keeps the room's subject clear of Nova's
 * bubble on any window shape, and sizes the bubble text so long bullets don't take
 * over the screen.
 *
 * Positions are in scene pixels of the FigmaStage (the 1463×823 Figma frame).
 * `view` is the part of that frame on screen; UI sizes (the bubble, Nova) are
 * converted with the overlay's scale relative to the scene.
 */
import type { ExplainLayout, Rect, SceneLayout } from '../constants/phenomena'

const FRAME_W = 1463
const FRAME_H = 823

/** ExplanationBubble.vue's box in overlay px (keep in sync with its CSS) */
export const BUBBLE = {
  width: 1008,
  /** top, right, bottom, left */
  padding: [16, 24, 16, 53] as const,
  border: 12,
  minHeight: 160,
  /** Gap between the bubble row and the window bottom */
  bottom: 24
}

/** Font sizes tried for a room's bullets, largest (the Figma size) first */
const FONT_SIZES = [30, 28, 26, 24]
/** A room's tallest bubble should stay within this; otherwise the smallest font is used */
const MAX_BUBBLE_HEIGHT = 210

export const bubbleLineHeight = (fontSize: number) => Math.round((fontSize * 38) / 30)

/**
 * Visible part of Nova peeking over the bubble's top-left (nova-peeking-hd.png's
 * opaque area): x relative to the window centre, and how far it rises above the
 * bubble top.
 */
const NOVA = { left: -479.5, right: -212.5, rise: 159 }

export interface BubbleFit {
  fontSize: number
  /** Height of the room's tallest bubble at that size (overlay px) */
  maxHeight: number
}

/** Largest font at which every bullet of the room fits a bubble of MAX_BUBBLE_HEIGHT */
export async function fitBubbleText(texts: string[]): Promise<BubbleFit> {
  try {
    await document.fonts.load('700 30px "Curio Mono"')
  } catch {
    // Measured with the fallback font instead
  }
  const [pt, pr, pb, pl] = BUBBLE.padding
  const box = document.createElement('div')
  Object.assign(box.style, {
    position: 'absolute',
    left: '-10000px',
    top: '0',
    visibility: 'hidden',
    width: `${BUBBLE.width}px`,
    minHeight: `${BUBBLE.minHeight}px`,
    boxSizing: 'border-box',
    padding: `${pt}px ${pr}px ${pb}px ${pl}px`,
    border: `${BUBBLE.border}px solid transparent`,
    display: 'flex',
    alignItems: 'center'
  })
  const line = document.createElement('p')
  Object.assign(line.style, {
    margin: '0',
    fontFamily: 'var(--curio-font-mono)',
    fontWeight: '700'
  })
  box.appendChild(line)
  document.body.appendChild(box)

  let fit: BubbleFit = { fontSize: FONT_SIZES[0]!, maxHeight: BUBBLE.minHeight }
  for (const fontSize of FONT_SIZES) {
    line.style.fontSize = `${fontSize}px`
    line.style.lineHeight = `${bubbleLineHeight(fontSize)}px`
    let maxHeight = BUBBLE.minHeight
    for (const text of texts) {
      line.textContent = text
      maxHeight = Math.max(maxHeight, box.offsetHeight)
    }
    fit = { fontSize, maxHeight }
    if (maxHeight <= MAX_BUBBLE_HEIGHT) break
  }
  box.remove()
  return fit
}

export interface View {
  left: number
  top: number
  right: number
  bottom: number
}

interface Placement {
  k: number
  tx: number
  ty: number
  /** The background covers the whole window */
  covers: boolean
  /** Window area above the bubble the background leaves uncovered */
  gap: number
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

/** Smallest k with k * room >= need */
const atLeast = (room: number, need: number) =>
  need <= 0 ? 0 : room > 0 ? need / room : Number.POSITIVE_INFINITY

const area = (r: View) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top)

const overlap = (a: View, b: View): View => ({
  left: Math.max(a.left, b.left),
  top: Math.max(a.top, b.top),
  right: Math.min(a.right, b.right),
  bottom: Math.min(a.bottom, b.bottom)
})

/**
 * Scale k and offset (tx, ty) that put `keep` inside `free`, staying as close to
 * the Figma frame as possible (frame centred, bottom on the window bottom, at the
 * UI's scale). 'fill' pictures also keep covering the window when they can.
 */
function place(explain: ExplainLayout, view: View, free: View, above: View): Placement | null {
  const [kx, ky, kw, kh] = explain.keep
  const [bx, by, bw, bh] = explain.background.rect
  const fill = explain.fit === 'fill'
  const vw = view.right - view.left
  const vh = view.bottom - view.top
  const fw = free.right - free.left
  const fh = free.bottom - free.top
  if (fw <= 0 || fh <= 0) return null

  // As large as fits; a 'fill' picture is zoomed in only as far as covering needs
  const kHi = Math.min(fw / kw, fh / kh)
  let k = kHi
  if (fill) {
    const r = Math.min(vw / FRAME_W, vh / FRAME_H)
    const kLo = Math.max(
      vw / bw,
      vh / bh,
      atLeast(by + bh - (ky + kh), view.bottom - free.bottom),
      atLeast(ky - by, free.top - view.top),
      atLeast(kx - bx, free.left - view.left),
      atLeast(bx + bw - (kx + kw), view.right - free.right)
    )
    k = Math.min(Math.max(r, kLo), kHi)
  }

  // Preferred offset, then (fill) the range that keeps the window covered, then the
  // range that keeps the subject inside `free`, which always wins
  const axis = (pref: number, keepLo: number, keepHi: number, coverLo: number, coverHi: number) => {
    let t = pref
    if (fill && coverLo <= coverHi) t = clamp(t, coverLo, coverHi)
    return clamp(t, keepLo, keepHi)
  }
  const tx = axis(
    (view.left + view.right) / 2 - (k * FRAME_W) / 2,
    free.left - k * kx,
    free.right - k * (kx + kw),
    view.right - k * (bx + bw),
    view.left - k * bx
  )
  const ty = axis(
    view.bottom - k * FRAME_H,
    free.top - k * ky,
    free.bottom - k * (ky + kh),
    view.bottom - k * (by + bh),
    view.top - k * by
  )

  const picture: View = {
    left: k * bx + tx,
    top: k * by + ty,
    right: k * (bx + bw) + tx,
    bottom: k * (by + bh) + ty
  }
  const covers =
    picture.left <= view.left + 0.5 &&
    picture.top <= view.top + 0.5 &&
    picture.right >= view.right - 0.5 &&
    picture.bottom >= view.bottom - 0.5
  return { k, tx, ty, covers, gap: area(above) - area(overlap(above, picture)) }
}

/**
 * The explanation scene for this window: `bubbleHeight` is the room's tallest
 * bubble (overlay px), so the scene stays put while the child steps through bullets.
 */
export function arrangeExplain(explain: ExplainLayout, view: View, bubbleHeight: number): SceneLayout {
  const vw = view.right - view.left
  const vh = view.bottom - view.top
  // Overlay px -> scene px
  const r = Math.min(vw / FRAME_W, vh / FRAME_H)
  const bubbleTop = view.bottom - r * (BUBBLE.bottom + bubbleHeight)
  const above: View = { ...view, bottom: bubbleTop }

  // As in Figma, Nova may overlap the scene's lower-left a little; with avoidNova
  // the subject goes either above Nova or to its right
  const frees: View[] =
    !explain.avoidNova
      ? [above]
      : [
          { ...view, bottom: bubbleTop - r * NOVA.rise },
          { ...view, left: (view.left + view.right) / 2 + r * NOVA.right, bottom: bubbleTop }
        ]
  let best: Placement | null = null
  const tolerance = area(above) * 0.01
  for (const free of frees) {
    const p = place(explain, view, free, above)
    if (!p) continue
    if (!best || p.gap < best.gap - tolerance || (Math.abs(p.gap - best.gap) <= tolerance && p.k > best.k)) {
      best = p
    }
  }
  if (!best) best = { k: r, tx: view.left, ty: view.top, covers: false, gap: 0 }

  const { k, tx, ty, covers } = best
  const map = ([x, y, w, h]: Rect): Rect => [k * x + tx, k * y + ty, k * w, k * h]
  const viewRect: Rect = [view.left, view.top, vw, vh]
  const background = { ...explain.background, rect: map(explain.background.rect) }

  const scene: SceneLayout = {
    background,
    // Card: the wash covers the whole window (it only shows over the card)
    wash: explain.fit === 'card' ? viewRect : explain.wash && map(explain.wash),
    washColor: explain.washColor,
    characters: explain.characters && { ...explain.characters, rect: map(explain.characters.rect) },
    icon: explain.icon && { ...explain.icon, rect: map(explain.icon.rect) }
  }

  if (explain.fit === 'fill' && !covers) {
    const [bx, by, bw, bh] = background.rect
    scene.extend = [
      by > view.top + 0.5,
      bx + bw < view.right - 0.5,
      by + bh < view.bottom - 0.5,
      bx > view.left + 0.5
    ]
  }
  return scene
}
