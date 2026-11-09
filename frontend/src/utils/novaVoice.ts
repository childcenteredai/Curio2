/**
 * Plays Nova's scripted lines through /api/speech, one after another.
 * All clips are requested up front so there is no gap between lines.
 */

/**
 * Synthesize one scripted line; resolves to an object URL (revoke it when done)
 * or null if speech failed. Scripted lines are the same for every child, so the
 * backend caches their audio.
 */
export const fetchClip = async (text: string): Promise<string | null> => {
  try {
    const res = await fetch('/api/speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, cache: true })
    })
    if (!res.ok) return null
    return URL.createObjectURL(await res.blob())
  } catch {
    return null
  }
}

/**
 * Nova's speaking rate. coral on gpt-4o-mini-tts ignores pacing instructions (tested:
 * asking for a quicker pace changed nothing), so the clips are sped up on playback.
 * Pitch is preserved, so she sounds like a quicker speaker, not a sped-up tape.
 */
export const NOVA_SPEECH_RATE = 1.15

/** Apply Nova's speaking rate to a clip before playing it */
export function atNovaRate(audio: HTMLAudioElement): HTMLAudioElement {
  audio.playbackRate = NOVA_SPEECH_RATE
  audio.preservesPitch = true
  return audio
}

/** Reading-time fallback when speech fails or autoplay is blocked */
export const readingDelay = (text: string) => 1200 + text.split(/\s+/).length * 320

export interface ClipPlayback {
  /** true once the clip played to the end, false if it could not play */
  finished: Promise<boolean>
  stop: () => void
}

/**
 * Play one clip at Nova's rate. onStart fires when sound starts, with the
 * wall-clock length of the line (fallbackMs if the browser can't tell), so text
 * can be typed out in step with the voice.
 */
export function playClip(
  url: string,
  fallbackMs: number,
  onStart: (durationMs: number) => void
): ClipPlayback {
  const clip = atNovaRate(new Audio(url))
  let resolveFinished: (played: boolean) => void = () => {}
  const finished = new Promise<boolean>(resolve => { resolveFinished = resolve })
  let started = false
  clip.onplaying = () => {
    if (started) return
    started = true
    const ms = (clip.duration * 1000) / NOVA_SPEECH_RATE
    onStart(Number.isFinite(ms) && ms > 0 ? ms : fallbackMs)
  }
  clip.onended = () => resolveFinished(true)
  clip.onerror = () => resolveFinished(started)
  clip.play().catch(() => resolveFinished(false))
  return {
    finished,
    stop: () => {
      clip.onplaying = null
      clip.pause()
      resolveFinished(false)
    }
  }
}

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
  let playback: ClipPlayback | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  const clips = lines.map(fetchClip)

  const wait = (ms: number) => new Promise<void>(r => { timer = setTimeout(r, ms) })

  const play = (url: string, fallbackMs: number, onStart: (durationMs: number) => void) => {
    playback = playClip(url, fallbackMs, onStart)
    return playback.finished
  }

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
      if (cancelled) return
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
      playback?.stop()
      playback = null
      clips.forEach(c => c.then(url => url && URL.revokeObjectURL(url)))
    }
  }
}
