<template>
  <FigmaStage :width="1463" :height="889" :crop-top="0.25">
    <!-- All map states stacked; only the active one is visible, so hover swaps instantly -->
    <img
      v-for="(src, key) in MAP.images"
      :key="key"
      class="map-layer"
      :class="{ visible: src === activeImage }"
      :src="src"
      alt=""
    />

    <template v-if="interactive">
      <button
        v-for="area in openAreas"
        :key="area"
        class="area-hitbox"
        :style="rectStyle(MAP.hitboxes[area])"
        :aria-label="`Explore the ${area}`"
        @mouseenter="hovered = area"
        @mouseleave="hovered = null"
        @focus="hovered = area"
        @blur="hovered = null"
        @click="enterArea(area)"
      />
    </template>

    <template #overlay>
      <div v-if="narrating || needsStart" class="wash" />
      <NarrativeBubble
        v-if="narrating"
        layout="map"
        :lines="lines"
        @done="finishIntro"
      />
      <!-- Direct-instruction version never uses the mic, but the first click is
           still needed so the browser lets Nova speak -->
      <button v-if="needsStart" class="start-button" @click="handleStart">Let's start!</button>

      <!-- Starts this version over from the very beginning (testers, a new run) -->
      <button v-if="canRestart" class="restart-button" @click="confirmingRestart = true">
        <span class="restart-icon" aria-hidden="true"><i class="fa-solid fa-rotate-left" /></span>
        Restart
      </button>
      <div
        v-if="confirmingRestart"
        class="restart-confirm"
        @click.self="confirmingRestart = false"
        @keydown.esc="confirmingRestart = false"
      >
        <div class="popup-card" role="dialog" aria-modal="true" aria-labelledby="restart-title">
          <div id="restart-title" class="confirm-title">Start over?</div>
          <div class="confirm-text">
            {{ restartFailed
              ? "Sorry, that didn't work. Please try again."
              : 'Your progress will be cleared and the adventure starts again from the beginning.' }}
          </div>
          <div class="confirm-actions">
            <button
              ref="cancelRestartButton"
              class="popup-button secondary"
              :disabled="restarting"
              @click="confirmingRestart = false"
            >
              Cancel
            </button>
            <button class="popup-button primary" :disabled="restarting" @click="restart">
              Restart
            </button>
          </div>
        </div>
      </div>
    </template>
  </FigmaStage>
  <MicCheckModal v-if="needsMicCheck" @done="handleMicCheckDone" />
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FigmaStage from '../components/FigmaStage.vue'
import NarrativeBubble from '../components/NarrativeBubble.vue'
import MicCheckModal from '../components/MicCheckModal.vue'
import { MAP, type Area } from '../constants/phenomena'
import { useAppVersion } from '../utils/appVersion'
import {
  fetchProgress,
  restartProgress,
  signOut,
  MIC_CHECK_SESSION_KEY,
  type Progress
} from '../utils/session'
import { rectStyle, introPlayed, markIntroPlayed } from '../utils/stage'

const DIRECT_STARTED_SESSION_KEY = 'curio_direct_started'
/** Nova's last line stays up this long before the child is signed out */
const GOODBYE_PAUSE_MS = 3000

const route = useRoute()
const router = useRouter()
const { version, areaPath, introKey: versionedKey } = useAppVersion()
// Goodbye screen after Finish Exploring: Nova's last words stay up, nothing is clickable
const ended = route.meta.ended === true

const progress = ref<Progress | null>(null)
const hovered = ref<Area | null>(null)
const narrating = ref(false)
const interactive = ref(false)
// Both chat versions (qa, teacher) use voice input
const needsMicCheck = ref(
  !ended && version.value !== 'direct' && sessionStorage.getItem(MIC_CHECK_SESSION_KEY) !== '1'
)
const needsStart = ref(
  !ended && version.value === 'direct' && sessionStorage.getItem(DIRECT_STARTED_SESSION_KEY) !== '1'
)

const completed = computed(() =>
  (['house', 'garden'] as Area[]).filter(a => progress.value?.[a].completed)
)
const openAreas = computed(() =>
  (['house', 'garden'] as Area[]).filter(a => !completed.value.includes(a))
)

// One area finished: Nova points the child at the other one
const lines = computed(() => {
  if (ended || !openAreas.value.length) return MAP.allDone
  if (completed.value.length === 1 && openAreas.value[0]) return MAP.returnVisit(openAreas.value[0])
  return MAP.firstVisit
})

const activeImage = computed(() => {
  // No artwork with both areas completed; nothing is clickable in that state
  if (!openAreas.value.length) return MAP.images.default
  if (completed.value.includes('house')) return MAP.images.houseCompleted
  if (completed.value.includes('garden')) return MAP.images.gardenCompleted
  if (!interactive.value) return MAP.images.default
  if (hovered.value === 'house') return MAP.images.houseHover
  if (hovered.value === 'garden') return MAP.images.gardenHover
  return MAP.images.default
})

const introKey = computed(() => versionedKey(`map:${completed.value.join(',')}`))

const startIntro = () => {
  if (ended) {
    narrating.value = true
  } else if (introPlayed(introKey.value)) {
    interactive.value = true
  } else {
    narrating.value = true
  }
}

// After the goodbye the child is signed out and lands on the lab's login page (the
// next sign-in opens the lab's app list, not this app). Without a sign-in (local
// dev) the goodbye screen just stays.
let leaveTimer: ReturnType<typeof setTimeout> | null = null
const leaveAfterGoodbye = () => {
  leaveTimer = setTimeout(async () => {
    const signOutPage = await signOut()
    if (signOutPage) window.location.assign(signOutPage)
  }, GOODBYE_PAUSE_MS)
}
onUnmounted(() => {
  if (leaveTimer) clearTimeout(leaveTimer)
})

const finishIntro = () => {
  if (ended) {
    leaveAfterGoodbye()
    return
  }
  markIntroPlayed(introKey.value)
  narrating.value = false
  interactive.value = true
}

// The mic check is the child's first click, which also unlocks audio autoplay for Nova
const handleMicCheckDone = () => {
  sessionStorage.setItem(MIC_CHECK_SESSION_KEY, '1')
  needsMicCheck.value = false
  startIntro()
}

const handleStart = () => {
  sessionStorage.setItem(DIRECT_STARTED_SESSION_KEY, '1')
  needsStart.value = false
  startIntro()
}

const enterArea = (area: Area) => {
  router.push(areaPath(area))
}

// Restart: not on the goodbye screen, and not behind the mic check / start button
const canRestart = computed(
  () => !ended && progress.value !== null && !needsMicCheck.value && !needsStart.value
)
const confirmingRestart = ref(false)
const restarting = ref(false)
const restartFailed = ref(false)
const cancelRestartButton = ref<HTMLButtonElement | null>(null)

watch(confirmingRestart, async open => {
  restartFailed.value = false
  if (open) {
    await nextTick()
    cancelRestartButton.value?.focus()
  }
})

// Reloads the page once the backend has recorded it: Nova stops, and the map
// comes back as a first visit (mic check or start button, then the first intro)
const restart = async () => {
  restarting.value = true
  if (await restartProgress(version.value)) {
    window.location.reload()
    return
  }
  restarting.value = false
  restartFailed.value = true
}

onMounted(async () => {
  progress.value = await fetchProgress(version.value)
  if (!needsMicCheck.value && !needsStart.value) startIntro()
})
</script>

<style scoped>
.map-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.25s ease;
}

.map-layer.visible {
  opacity: 1;
}

.area-hitbox {
  position: absolute;
  padding: 0;
  border: none;
  border-radius: 24px;
  background: transparent;
  cursor: pointer;
}

.area-hitbox:focus-visible {
  outline: 6px solid var(--curio-yellow);
}

.wash {
  position: absolute;
  inset: 0;
  background: rgba(255, 249, 239, 0.45);
}

/* Restart, top-right corner: same look as the Back to Map / Finish Exploring
   buttons (glossy yellow pill, dark outline, sticker icon, blue on hover), built in
   CSS since there is no exported art for it */
.restart-button {
  --pill-top: #ffe25a;
  --pill-mid: #ffc61a;
  --pill-bottom: #ff9d0a;
  position: absolute;
  right: 30px;
  top: 26px;
  display: flex;
  align-items: center;
  height: 58px;
  padding: 0 38px 0 66px;
  border: 4px solid #0b2038;
  border-radius: 999px;
  background: linear-gradient(var(--pill-top), var(--pill-mid) 55%, var(--pill-bottom));
  box-shadow:
    inset 0 -5px 0 rgba(214, 96, 0, 0.35),
    0 0 0 3px rgba(255, 249, 220, 0.9);
  font-family: var(--curio-font-round);
  font-weight: 700;
  font-size: 28px;
  color: #0b2038;
  -webkit-text-stroke: 0.6px #0b2038;
  text-shadow:
    2px 0 0 #fff, -2px 0 0 #fff, 0 2px 0 #fff, 0 -2px 0 #fff,
    1.5px 1.5px 0 #fff, -1.5px 1.5px 0 #fff, 1.5px -1.5px 0 #fff, -1.5px -1.5px 0 #fff;
  cursor: pointer;
  transition: transform 0.15s ease;
}

/* Glossy highlight at the right end of the pill */
.restart-button::after {
  content: '';
  position: absolute;
  right: 11px;
  top: 8px;
  width: 13px;
  height: 12px;
  border-top: 4px solid rgba(255, 255, 255, 0.95);
  border-right: 4px solid rgba(255, 255, 255, 0.95);
  border-radius: 0 14px 0 0;
}

.restart-button:hover {
  --pill-top: #5cc0ff;
  --pill-mid: #2196f3;
  --pill-bottom: #0b62d6;
  box-shadow:
    inset 0 -5px 0 rgba(0, 48, 140, 0.35),
    0 0 0 3px rgba(255, 249, 220, 0.9);
}

.restart-button:active {
  transform: scale(0.97);
}

.restart-button:focus-visible {
  outline: 6px solid var(--curio-blue-rim);
  outline-offset: 4px;
}

/* Sticker icon overhanging the pill's left end, with the two spark marks */
.restart-icon {
  position: absolute;
  left: -14px;
  top: 50%;
  width: 66px;
  height: 66px;
  display: grid;
  place-items: center;
  border: 4px solid #0b2038;
  border-radius: 50%;
  background: linear-gradient(#4fb3ff, #1f6fe0);
  box-shadow: 0 0 0 4px #fff;
  transform: translateY(-50%) rotate(-12deg);
  color: #fff;
  font-size: 30px;
  -webkit-text-stroke: 0;
  text-shadow: 0 2px 0 #0b2038;
}

.restart-icon::before,
.restart-icon::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 18px;
  border-radius: 4px;
  background: #ffd21f;
  box-shadow: 0 0 0 2.5px #fff;
}

.restart-icon::before {
  right: -8px;
  top: -16px;
  transform: rotate(32deg);
}

.restart-icon::after {
  right: -24px;
  top: -4px;
  transform: rotate(62deg);
}

.restart-confirm {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 30, 50, 0.45);
}

.confirm-title {
  font-weight: 700;
  font-size: 40px;
  margin-bottom: 10px;
}

.confirm-text {
  font-weight: 600;
  font-size: 26px;
  line-height: 1.4;
  margin-bottom: 32px;
}

.confirm-actions {
  display: flex;
  justify-content: center;
  gap: 32px;
}

/* Same look as the popup buttons, larger */
.start-button {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  min-width: 360px;
  height: 104px;
  padding: 0 48px;
  border: 6px solid var(--curio-navy);
  border-radius: 999px;
  background: var(--curio-yellow);
  box-shadow: 0 7px 0 var(--curio-navy);
  font-family: var(--curio-font-mono);
  font-weight: 700;
  font-size: 40px;
  color: var(--curio-navy);
  cursor: pointer;
  transition: filter 0.15s ease, box-shadow 0.15s ease;
}

.start-button:hover {
  filter: brightness(1.05);
}

.start-button:active {
  box-shadow: 0 2px 0 var(--curio-navy);
  translate: 0 5px;
}

.start-button:focus-visible {
  outline: 6px solid var(--curio-blue-rim);
  outline-offset: 4px;
}
</style>
