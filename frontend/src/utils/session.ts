import type { Area } from '../constants/phenomena'

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

export async function fetchProgress(): Promise<Progress> {
  try {
    const res = await fetch(`/api/progress?session_id=${encodeURIComponent(getOrCreateSessionId())}`)
    if (!res.ok) return EMPTY
    const data = await res.json()
    return { ...EMPTY, ...data.areas }
  } catch {
    return EMPTY
  }
}
