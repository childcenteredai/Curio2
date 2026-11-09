import { ref, onUnmounted } from 'vue'

/**
 * Types a line out in step with Nova's voice: `typed` characters are shown, and
 * the text finishes just before the spoken line does.
 */
export function useTypewriter() {
  const typed = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  const stop = () => {
    if (timer) clearInterval(timer)
    timer = null
  }

  const type = (total: number, durationMs: number) => {
    stop()
    typed.value = 0
    const startedAt = performance.now()
    const span = Math.max(durationMs * 0.9, 300)
    timer = setInterval(() => {
      typed.value = Math.min(total, Math.ceil((total * (performance.now() - startedAt)) / span))
      if (typed.value >= total) stop()
    }, 30)
  }

  /** Show the whole line at once */
  const finish = (total: number) => {
    stop()
    typed.value = total
  }

  /** Hide the line (e.g. while its voice is still loading) */
  const clear = () => {
    stop()
    typed.value = 0
  }

  onUnmounted(stop)
  return { typed, type, finish, clear, stop }
}
