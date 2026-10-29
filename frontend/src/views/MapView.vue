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
      <div v-if="narrating" class="wash" />
      <NarrativeBubble
        v-if="narrating"
        layout="map"
        :lines="lines"
        @done="finishIntro"
      />
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
import { fetchProgress, MIC_CHECK_SESSION_KEY, type Progress } from '../utils/session'
import { rectStyle, introPlayed, markIntroPlayed } from '../utils/stage'

const router = useRouter()

const progress = ref<Progress | null>(null)
const hovered = ref<Area | null>(null)
const narrating = ref(false)
const interactive = ref(false)
const needsMicCheck = ref(sessionStorage.getItem(MIC_CHECK_SESSION_KEY) !== '1')

const completed = computed(() =>
  (['house', 'garden'] as Area[]).filter(a => progress.value?.[a].completed)
)
const openAreas = computed(() =>
  (['house', 'garden'] as Area[]).filter(a => !completed.value.includes(a))
)

// Second session: one area is done, so Nova points the child at the other one
const lines = computed(() =>
  completed.value.length === 1 && openAreas.value[0]
    ? MAP.returnVisit(openAreas.value[0])
    : MAP.firstVisit
)

const activeImage = computed(() => {
  if (completed.value.includes('house')) return MAP.images.houseCompleted
  if (completed.value.includes('garden')) return MAP.images.gardenCompleted
  if (!interactive.value) return MAP.images.default
  if (hovered.value === 'house') return MAP.images.houseHover
  if (hovered.value === 'garden') return MAP.images.gardenHover
  return MAP.images.default
})

const introKey = computed(() => `map:${completed.value.join(',')}`)

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

const enterArea = (area: Area) => {
  router.push(`/area/${area}`)
}

onMounted(async () => {
  progress.value = await fetchProgress()
  if (!needsMicCheck.value) startIntro()
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
</style>
