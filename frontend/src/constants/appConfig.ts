/**
 * App version: 1 = bubbles on match only; 2 = all bubbles visible (gray), light up on match
 * User can switch via UI; stored in localStorage. Falls back to /api/config if not set.
 */
import { ref, computed } from 'vue'

const STORAGE_KEY = 'curio_app_version'

const curioAppVersion = ref<1 | 2>(1)

function initFromStorage(): void {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === '2') curioAppVersion.value = 2
    else if (stored === '1') curioAppVersion.value = 1
  } catch {
    // keep default
  }
}

export function setCurioAppVersion(v: 1 | 2): void {
  curioAppVersion.value = v
  try {
    localStorage.setItem(STORAGE_KEY, String(v))
  } catch {
    // ignore
  }
}

export async function loadAppConfig(): Promise<void> {
  initFromStorage()
  try {
    const res = await fetch('/api/config')
    if (res.ok) {
      const data = await res.json()
      const v = data?.curio_app_version
      // Only use API if user hasn't set a preference in localStorage
      if (localStorage.getItem(STORAGE_KEY) == null) {
        if (v === 2) curioAppVersion.value = 2
        else curioAppVersion.value = 1
      }
    }
  } catch {
    // keep current (from storage or default)
  }
}

export const CURIO_APP_VERSION = computed(() => curioAppVersion.value)
