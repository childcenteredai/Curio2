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
    </template>
  </FigmaStage>
  <MicCheckModal v-if="needsMicCheck" @done="handleMicCheckDone" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import FigmaStage from '../components/FigmaStage.vue'
import NarrativeBubble from '../components/NarrativeBubble.vue'
import MicCheckModal from '../components/MicCheckModal.vue'
import { MAP, type Area } from '../constants/phenomena'
import { useAppVersion } from '../utils/appVersion'
import { fetchProgress, MIC_CHECK_SESSION_KEY, type Progress } from '../utils/session'
import { rectStyle, introPlayed, markIntroPlayed } from '../utils/stage'

const DIRECT_STARTED_SESSION_KEY = 'curio_direct_started'

const router = useRouter()
const { version, areaPath, introKey: versionedKey } = useAppVersion()

const progress = ref<Progress | null>(null)
const hovered = ref<Area | null>(null)
const narrating = ref(false)
const interactive = ref(false)
// Both chat versions (qa, teacher) use voice input
const needsMicCheck = ref(
  version.value !== 'direct' && sessionStorage.getItem(MIC_CHECK_SESSION_KEY) !== '1'
)
const needsStart = ref(
  version.value === 'direct' && sessionStorage.getItem(DIRECT_STARTED_SESSION_KEY) !== '1'
)

const completed = computed(() =>
  (['house', 'garden'] as Area[]).filter(a => progress.value?.[a].completed)
)
const openAreas = computed(() =>
  (['house', 'garden'] as Area[]).filter(a => !completed.value.includes(a))
)

// One area finished: Nova points the child at the other one
const lines = computed(() => {
  if (!openAreas.value.length) return MAP.allDone
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
  if (introPlayed(introKey.value)) {
    interactive.value = true
  } else {
    narrating.value = true
  }
}

const finishIntro = () => {
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
