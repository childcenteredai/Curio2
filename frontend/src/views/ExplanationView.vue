<template>
  <FigmaStage v-if="phenomenon">
    <template #default="{ visible }">
      <SceneLayers :layout="sceneFor(visible)" :glide="gliding" :alt="phenomenon.label" />
    </template>

    <template #overlay>
      <!-- 4-1: the child looks at the illustration with the researcher, then asks Nova -->
      <Transition name="pop">
        <button
          v-if="phase === 'look'"
          class="listen-button"
          aria-label="Listen to Nova"
          :disabled="!bullets.length"
          @click="listen"
        >
          <img src="/imgs/ui/listen-to-nova-button.png" alt="" />
        </button>
      </Transition>

      <!-- 4-2: Nova explains, one bullet (knowledge component) at a time -->
      <Transition name="pop">
        <button
          v-if="phase === 'explain'"
          class="back-to-area"
          :aria-label="`Back to the ${area.label}`"
          @click="exit"
        >
          <img :src="area.backButton" alt="" />
        </button>
      </Transition>
      <Transition name="rise">
        <ExplanationBubble
          v-if="bubbleShown"
          :text="currentText"
          :typed="typed"
          :can-go-back="step > 0"
          :is-last="step === bullets.length - 1"
          :ready="spoken"
          :font-size="bubbleFit.fontSize"
          @back="goBack"
          @next="goNext"
        />
      </Transition>
    </template>
  </FigmaStage>
</template>

<script setup lang="ts">
/**
 * Room screen of the direct-instruction version (/direct/area/:area/:phenomenon).
 * The illustration is shown large first; "Listen to Nova" moves it up and Nova
 * narrates the explanation bullet by bullet, with the child stepping back and
 * forth using the arrows.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FigmaStage from '../components/FigmaStage.vue'
import SceneLayers from '../components/SceneLayers.vue'
import ExplanationBubble from '../components/ExplanationBubble.vue'
import { AREAS, PHENOMENA } from '../constants/phenomena'
import { useAppVersion } from '../utils/appVersion'
import { fetchClip, playClip, readingDelay, type ClipPlayback } from '../utils/novaVoice'
import {
  fetchExplanation,
  logExplanationEvent,
  type ExplanationAction,
  type ExplanationBullet
} from '../utils/session'
import { useTypewriter } from '../utils/typewriter'
import { BUBBLE, arrangeExplain, fitBubbleText, type BubbleFit, type View } from '../utils/explainLayout'

/** Time for the illustration to glide into place before Nova starts */
const GLIDE_MS = 900

const route = useRoute()
const router = useRouter()
const { mapPath, areaPath } = useAppVersion()

const phenomenon = computed(() => {
  const p = PHENOMENA[route.params.phenomenon as string]
  return p && p.area === route.params.area ? p : undefined
})
const area = computed(() => AREAS[phenomenon.value?.area ?? 'house'])

const phase = ref<'look' | 'explain'>('look')
/** Room's bubble text size and tallest bubble, measured once its bullets load */
const bubbleFit = ref<BubbleFit>({ fontSize: 30, maxHeight: BUBBLE.minHeight })
// The illustration glides into place when Nova starts; afterwards it just follows
// the window size
const gliding = ref(false)
let glideTimer: ReturnType<typeof setTimeout> | null = null

/** 4-1: the room as in Figma's phenomenon frame; 4-2: fitted above the bubble for this window */
const sceneFor = (visible: View) => {
  const p = phenomenon.value!
  if (phase.value === 'look') return p.look ?? p.intro
  return arrangeExplain(p.explain, visible, bubbleFit.value.maxHeight)
}

const bullets = ref<ExplanationBullet[]>([])
const step = ref(0)
const currentText = computed(() => bullets.value[step.value]?.text ?? '')
const bubbleShown = ref(false)
/** Nova has finished speaking the current bullet */
const spoken = ref(false)
const { typed, type, finish, clear } = useTypewriter()

// Voice for every bullet is requested as soon as the room opens, while the child
// is still looking at the illustration, so Nova starts without a wait
let clips: Promise<string | null>[] = []
let playback: ClipPlayback | null = null
let speakToken = 0
let timer: ReturnType<typeof setTimeout> | null = null
let completeLogged: Promise<void> | null = null
let leaving = false

const wait = (ms: number) => new Promise<void>(resolve => { timer = setTimeout(resolve, ms) })

const log = (action: ExplanationAction, at = step.value) => {
  if (!phenomenon.value) return Promise.resolve()
  return logExplanationEvent(phenomenon.value.id, action, at)
}

const stopSpeaking = () => {
  speakToken++
  playback?.stop()
  playback = null
  if (timer) clearTimeout(timer)
  timer = null
}

const speak = async (index: number) => {
  stopSpeaking()
  const token = speakToken
  spoken.value = false
  clear()
  const line = bullets.value[index]?.text ?? ''
  const fallbackMs = readingDelay(line)

  const url = await clips[index]
  if (token !== speakToken) return
  if (url) {
    playback = playClip(url, fallbackMs, ms => type(line.length, ms))
    const played = await playback.finished
    if (token !== speakToken) return
    if (played) {
      finish(line.length)
      spoken.value = true
      return
    }
  }
  // No voice (speech failed or audio blocked): type the bullet at reading speed
  type(line.length, fallbackMs)
  await wait(fallbackMs)
  if (token === speakToken) spoken.value = true
}

/** Show a bullet; reaching the last one counts the room as explored ("Done!") */
const show = (index: number) => {
  step.value = index
  if (index === bullets.value.length - 1 && !completeLogged) {
    completeLogged = log('complete', index)
  }
  speak(index)
}

const listen = async () => {
  if (!bullets.value.length || phase.value !== 'look') return
  log('listen', 0)
  gliding.value = true
  if (glideTimer) clearTimeout(glideTimer)
  glideTimer = setTimeout(() => { gliding.value = false }, GLIDE_MS + 200)
  phase.value = 'explain'
  await wait(GLIDE_MS)
  if (leaving) return
  bubbleShown.value = true
  show(0)
}

const goNext = () => {
  if (step.value < bullets.value.length - 1) {
    log('next', step.value + 1)
    show(step.value + 1)
  } else {
    // Past the last bullet: back to the rooms
    exit()
  }
}

const goBack = () => {
  if (step.value === 0) return
  log('back', step.value - 1)
  show(step.value - 1)
}

const exit = async () => {
  if (leaving) return
  leaving = true
  stopSpeaking()
  // Wait (briefly) for the writes, so the room already shows "Done!" on arrival
  const writes = Promise.all([log('exit'), completeLogged])
  await Promise.race([writes, new Promise(resolve => setTimeout(resolve, 1500))])
  router.push(areaPath(area.value.id))
}

const releaseClips = () => {
  clips.forEach(c => c.then(url => url && URL.revokeObjectURL(url)))
  clips = []
}

watch(
  phenomenon,
  async p => {
    stopSpeaking()
    releaseClips()
    phase.value = 'look'
    bubbleShown.value = false
    bullets.value = []
    completeLogged = null
    leaving = false
    if (!p) {
      router.replace(mapPath.value)
      return
    }
    const loaded = await fetchExplanation(p.id)
    if (phenomenon.value !== p) return
    // Sized before "Listen to Nova" can be pressed, so the scene moves only once
    const fit = await fitBubbleText(loaded.map(b => b.text))
    if (phenomenon.value !== p) return
    bubbleFit.value = fit
    bullets.value = loaded
    clips = loaded.map(b => fetchClip(b.text))
  },
  { immediate: true }
)

onUnmounted(() => {
  if (glideTimer) clearTimeout(glideTimer)
  leaving = true
  stopSpeaking()
  releaseClips()
})
</script>

<style scoped>
/* Top-left, where the room button sits once Nova is explaining. The exported art
   (445×187) has transparent margins, so the button box is the art's bbox
   (28,10 → 403,174) and the image overhangs it. */
.listen-button {
  position: absolute;
  left: 28px;
  top: 30px;
  width: 375px;
  height: 164px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  animation: beckon 1.8s ease-in-out infinite;
  transition: filter 0.15s ease;
}

.listen-button img {
  position: absolute;
  left: -28px;
  top: -10px;
  width: 445px;
  height: 187px;
  max-width: none;
  pointer-events: none;
}

.listen-button:hover {
  animation-play-state: paused;
  filter: brightness(1.05) drop-shadow(0 0 10px rgba(255, 211, 77, 0.9));
}

.listen-button:active {
  translate: 0 3px;
}

.listen-button:disabled {
  cursor: wait;
  animation: none;
  opacity: 0.7;
}

.listen-button:focus-visible {
  outline: 6px solid var(--curio-yellow);
  outline-offset: 3px;
  border-radius: 40px;
}

@keyframes beckon {
  50% { transform: scale(1.05); }
}

/* "Room Selection Button" / "outdoor button" instances */
.back-to-area {
  position: absolute;
  left: 28px;
  top: 30px;
  width: 126px;
  height: 121px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.back-to-area:hover {
  transform: scale(1.06);
}

.back-to-area img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.pop-enter-active {
  transition: transform 0.4s ease, opacity 0.4s ease;
  transition-delay: 0.5s;
}

.pop-leave-active {
  transition: opacity 0.2s ease;
}

.pop-enter-from {
  transform: scale(0.6);
  opacity: 0;
}

.pop-leave-to {
  opacity: 0;
}

.rise-enter-active {
  transition: transform 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.2), opacity 0.4s ease;
}

.rise-enter-from {
  transform: translateY(60px);
  opacity: 0;
}
</style>
