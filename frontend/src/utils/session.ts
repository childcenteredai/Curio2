import type { Area } from '../constants/phenomena'
import type { AppVersion } from './appVersion'

const SESSION_KEY = 'curio_session_id'
export const MIC_CHECK_SESSION_KEY = 'curio_mic_check_completed'

/** Browser-level id; the backend prefers the logged-in user when a JWT is present */
export function getOrCreateSessionId(): string {
  const stored = localStorage.getItem(SESSION_KEY)
  if (stored) return stored
  const id = crypto.randomUUID()
  localStorage.setItem(SESSION_KEY, id)
  return id
}

export interface AreaProgress {
  explored: string[]
  completed: boolean
}

export type Progress = Record<Area, AreaProgress>

const EMPTY: Progress = {
  house: { explored: [], completed: false },
  garden: { explored: [], completed: false }
}

/** Record a "Finish Exploring" click; the area then shows as completed on the map */
export async function finishArea(area: Area, version: AppVersion = 'qa'): Promise<boolean> {
  try {
    const res = await fetch('/api/progress/finish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ area, version, session_id: getOrCreateSessionId() })
    })
    return res.ok
  } catch (error) {
    console.error('Failed to record finished area:', error)
    return false
  }
}

/** Progress is kept per version: each child uses one version for both sessions */
export async function fetchProgress(version: AppVersion = 'qa'): Promise<Progress> {
  try {
    const params = new URLSearchParams({ session_id: getOrCreateSessionId(), version })
    const res = await fetch(`/api/progress?${params}`)
    if (!res.ok) return EMPTY
    const data = await res.json()
    return { ...EMPTY, ...data.areas }
  } catch {
    return EMPTY
  }
}

/** One bullet of Nova's explanation, tied to the knowledge component it covers */
export interface ExplanationBullet {
  concept: string
  text: string
}

export async function fetchExplanation(phenomenon: string): Promise<ExplanationBullet[]> {
  try {
    const res = await fetch(`/api/explanations/${encodeURIComponent(phenomenon)}`)
    if (!res.ok) return []
    return (await res.json()).bullets ?? []
  } catch {
    return []
  }
}

/**
 * Log a step through the explanation. 'complete' (reached the last bullet) is what
 * marks the room "Done!" in the direct-instruction version.
 */
export type ExplanationAction = 'listen' | 'next' | 'back' | 'complete' | 'exit'

export async function logExplanationEvent(
  phenomenon: string,
  action: ExplanationAction,
  step: number
): Promise<void> {
  try {
    await fetch(`/api/explanations/${encodeURIComponent(phenomenon)}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, step, session_id: getOrCreateSessionId() }),
      // Still sent when the click navigates away (back to the rooms)
      keepalive: true
    })
  } catch (error) {
    console.error(`Failed to log explanation ${action}:`, error)
  }
}
