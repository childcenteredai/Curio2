/**
 * Plays Nova's scripted lines through /api/speech, one after another.
 * All clips are requested up front so there is no gap between lines.
 */

const fetchClip = async (text: string): Promise<string | null> => {
  try {
    const res = await fetch('/api/speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    if (!res.ok) return null
    return URL.createObjectURL(await res.blob())
  } catch {
    return null
  }
}

/** Reading-time fallback when speech fails or autoplay is blocked */
const readingDelay = (text: string) => 1200 + text.split(/\s+/).length * 320

export interface Narration {
  cancel: () => void
}

/**
 * onLine fires when a line starts, with how long it will be spoken (ms), so the
 * bubble can type the text out in step with the voice.
 */
export function narrate(
  lines: string[],
  onLine: (index: number, durationMs: number) => void,
  onDone: () => void
): Narration {
  let cancelled = false
  let audio: HTMLAudioElement | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  const clips = lines.map(fetchClip)

  const wait = (ms: number) => new Promise<void>(r => { timer = setTimeout(r, ms) })

  const play = (url: string, fallbackMs: number, onStart: (durationMs: number) => void) =>
    new Promise<boolean>(resolve => {
      const clip = new Audio(url)
      audio = clip
      let started = false
      clip.onplaying = () => {
        if (started) return
        started = true
        const ms = clip.duration * 1000
        onStart(Number.isFinite(ms) && ms > 0 ? ms : fallbackMs)
      }
      clip.onended = () => resolve(true)
      clip.onerror = () => resolve(started)
      clip.play().catch(() => resolve(false))
    })

  ;(async () => {
    for (const [i, line] of lines.entries()) {
      if (cancelled) return
      const url = await clips[i]
      if (cancelled) return
      let shown = false
      const played = url
        ? await play(url, readingDelay(line), ms => { shown = true; onLine(i, ms) })
        : false
      if (url) URL.revokeObjectURL(url)
      if (!played) {
        // No voice: still type the line out, at reading speed
        const ms = readingDelay(line)
        if (!shown) onLine(i, ms)
        await wait(ms)
      }
      // Short beat between lines
      if (i < lines.length - 1) await wait(350)
    }
    if (!cancelled) onDone()
  })()

  return {
    cancel: () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      if (audio) {
        audio.pause()
        audio = null
      }
      clips.forEach(c => c.then(url => url && URL.revokeObjectURL(url)))
    }
  }
}
