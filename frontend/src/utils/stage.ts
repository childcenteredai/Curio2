import type { Rect } from '../constants/phenomena'

/** Absolute position for a Figma [x, y, w, h] rect inside a FigmaStage */
export const rectStyle = ([x, y, w, h]: Rect) => ({
  left: `${x}px`,
  top: `${y}px`,
  width: `${w}px`,
  height: `${h}px`
})

const INTRO_PLAYED_KEY = 'curio_intro_played'

/** Scripted intros play once per browser session (not every time the child comes back) */
export function introPlayed(id: string): boolean {
  try {
    return JSON.parse(sessionStorage.getItem(INTRO_PLAYED_KEY) || '[]').includes(id)
  } catch {
    return false
  }
}

export function markIntroPlayed(id: string): void {
  try {
    const played: string[] = JSON.parse(sessionStorage.getItem(INTRO_PLAYED_KEY) || '[]')
    if (!played.includes(id)) played.push(id)
    sessionStorage.setItem(INTRO_PLAYED_KEY, JSON.stringify(played))
  } catch {
    // Storage blocked: the intro just plays again next time
  }
}
