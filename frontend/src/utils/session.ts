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

/** Goodbye screen of an activity that ended on this page load */
let endedAt: string | null = null

/**
 * End of the child's activity (Finish Exploring). Until the page is loaded again
 * (a new tab, a refresh, the next login), every navigation, browser back included,
 * lands on the goodbye screen at `goodbyePath`. What this tab has seen (intros
 * heard, mic check, the 30-minute clock, all kept as curio_* keys) is forgotten,
 * so the next session started here begins like a fresh visit.
 */
export function endActivity(goodbyePath: string): void {
  endedAt = goodbyePath
  forgetTab()
}

/** Forgets what this tab has seen (intros heard, mic check, the 30-minute clock) */
function forgetTab(): void {
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith('curio_')) sessionStorage.removeItem(key)
    }
  } catch {
    // Storage blocked: nothing was kept
  }
}

/**
 * "Restart" on the map: this version's progress starts over for the logged-in user
 * (else this browser), and this tab forgets what it has seen, so the next page
 * load is a first visit. Earlier records stay in the database. Resolves to false
 * if the backend didn't record it (progress unchanged).
 */
export async function restartProgress(version: AppVersion): Promise<boolean> {
  try {
    const res = await fetch('/api/progress/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version, session_id: getOrCreateSessionId() })
    })
    if (!res.ok) return false
  } catch {
    return false
  }
  forgetTab()
  return true
}

export const activityEndedAt = () => endedAt

/**
 * Sign the child out of the lab login (backend /api/auth/sign-out). Resolves to the
 * lab's logout page to send the browser to, which ends with the login page, or null
 * when there is no sign-in to end (e.g. local dev).
 */
export async function signOut(): Promise<string | null> {
  try {
    const res = await fetch('/api/auth/sign-out', { method: 'POST' })
    if (!res.ok) return null
    return (await res.json()).redirect ?? null
  } catch {
    return null
  }
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
