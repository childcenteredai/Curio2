import { computed } from 'vue'
import { useRoute } from 'vue-router'

/**
 * App versions served side by side (ids match backend/phenomena.py VERSIONS):
 * - 'qa': question-asking with AI, at /
 * - 'direct': direct instruction with AI, at /direct
 * - 'teacher': the question-asking chat run by a teacher, at /teacher. Only the
 *   map, room selection and chat: no Nova character or narration on those screens,
 *   Nova's chat replies are text only, and voice input is transcribed into a box
 *   the teacher can edit before sending.
 * All share the map and room-selection screens; only the room screen differs.
 */
export type AppVersion = 'qa' | 'direct' | 'teacher'

const BASE: Record<AppVersion, string> = { qa: '', direct: '/direct', teacher: '/teacher' }

/** The current route's version (set in router meta) and paths that stay inside it */
export function useAppVersion() {
  const route = useRoute()
  const version = computed<AppVersion>(() => (route.meta.version as AppVersion | undefined) ?? 'qa')
  const base = computed(() => BASE[version.value])

  return {
    version,
    mapPath: computed(() => base.value || '/'),
    /** Nova (the character and her spoken lines) on the map, area screens and
     *  popups; the teacher version has none, only her text replies in the chat */
    hasNova: computed(() => version.value !== 'teacher'),
    /** Goodbye screen after Finish Exploring */
    donePath: computed(() => `${base.value}/done`),
    areaPath: (area: string) => `${base.value}/area/${area}`,
    roomPath: (area: string, room: string) => `${base.value}/area/${area}/${room}`,
    /** Scripted intros are tracked per version, so testing one doesn't skip the other's */
    introKey: (key: string) => (version.value === 'qa' ? key : `${version.value}:${key}`)
  }
}
