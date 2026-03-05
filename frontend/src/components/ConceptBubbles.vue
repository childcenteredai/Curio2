<template>
  <div v-if="shouldShow" ref="wrapperRef" class="concept-bubbles-wrapper">
    <Teleport to="body">
      <div
        v-if="tooltip.concept"
        class="concept-tooltip"
        :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
      >
        <div class="concept-tooltip-title">{{ tooltip.concept }}</div>
        <div class="concept-tooltip-body">{{ tooltip.explanation }}</div>
      </div>
    </Teleport>
    <svg
      class="connection-lines"
      :viewBox="`0 0 ${wrapperSize.width} ${wrapperSize.height}`"
      preserveAspectRatio="none"
    >
      <path
        v-for="(path, i) in connectionPaths"
        :key="i"
        :d="path.d"
        class="connection-path"
        :class="{ visible: path.visible }"
      />
    </svg>
    <div class="concept-bubbles">
      <div
        v-for="slot in slots"
        :key="slot.concept"
        :ref="(el) => setSlotRef(el, slot.conceptIndex)"
        class="bubble-slot"
        :class="{ 'slot-filled': slot.matched }"
        :style="slot.gridStyle"
      >
        <span
          v-if="slot.matched"
          class="concept-bubble"
          :class="{ 'concept-bubble-enter': newlyEnteredConcepts.has(slot.concept) }"
          :style="{ animationDelay: `${slot.conceptIndex * 0.06}s` }"
          @mouseenter="onBubbleEnter($event, slot.concept)"
          @mousemove="onBubbleMove($event)"
          @mouseleave="onBubbleLeave"
        >
          {{ slot.concept }}
        </span>
        <span
          v-else-if="isVersion2"
          class="concept-bubble concept-bubble-gray"
          aria-hidden="true"
        ></span>
        <span v-else class="bubble-placeholder" aria-hidden="true"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  CONCEPT_ORDER,
  CONCEPT_GRID_POSITIONS,
  CONCEPT_CONNECTIONS,
} from '../constants/conceptOrder'
import { CURIO_APP_VERSION, loadAppConfig } from '../constants/appConfig'

const isVersion2 = computed(() => CURIO_APP_VERSION.value === 2)

const props = defineProps<{
  conceptOrder: readonly string[]
  matchedConcepts: Set<string>
  phenomenon?: string
}>()

const wrapperRef = ref<HTMLElement | null>(null)
const slotRefs = ref<(HTMLElement | null)[]>([])
const wrapperSize = ref({ width: 620, height: 380 })

const conceptExplanations = ref<Record<string, string>>({})
const newlyEnteredConcepts = ref<Set<string>>(new Set())
const prevMatchedConcepts = ref<Set<string>>(new Set())
const ENTER_ANIMATION_DURATION = 1800

const tooltip = ref<{ concept: string; explanation: string; x: number; y: number }>({
  concept: '',
  explanation: '',
  x: 0,
  y: 0,
})

const TOOLTIP_OFFSET = 16

const setSlotRef = (el: unknown, index: number) => {
  if (el) {
    slotRefs.value[index] = el as HTMLElement
  }
}

async function fetchConceptExplanations() {
  const p = props.phenomenon || 'balloon'
  try {
    const res = await fetch(`/api/knowledge/concepts?phenomenon=${p}`)
    if (res.ok) {
      const data = await res.json()
      const map: Record<string, string> = {}
      for (const [name, obj] of Object.entries(data)) {
        const exp = (obj as { explanation?: string }).explanation
        if (exp) map[name] = exp
      }
      conceptExplanations.value = map
    }
  } catch {
    conceptExplanations.value = {}
  }
}

function onBubbleEnter(e: MouseEvent, concept: string) {
  const exp = conceptExplanations.value[concept]
  if (!exp) return
  tooltip.value = {
    concept,
    explanation: exp,
    x: e.clientX + TOOLTIP_OFFSET,
    y: e.clientY + TOOLTIP_OFFSET,
  }
}

function onBubbleMove(e: MouseEvent) {
  if (!tooltip.value.concept) return
  tooltip.value = {
    ...tooltip.value,
    x: e.clientX + TOOLTIP_OFFSET,
    y: e.clientY + TOOLTIP_OFFSET,
  }
}

function onBubbleLeave() {
  tooltip.value = { concept: '', explanation: '', x: 0, y: 0 }
}

const shouldShow = computed(() => {
  if (isVersion2.value) return true
  return props.matchedConcepts.size > 0
})

const slots = computed(() => {
  const v2 = isVersion2.value
  const order = v2 ? [...CONCEPT_ORDER] : [...props.conceptOrder]
  const matched = props.matchedConcepts
  const conceptsToShow = v2 ? order : order.filter((c) => matched.has(c))

  return conceptsToShow.map((concept) => {
    const conceptIndex = order.indexOf(concept)
    const pos = CONCEPT_GRID_POSITIONS[conceptIndex] ?? [1, 1]
    const [row, col] = pos
    return {
      concept,
      conceptIndex,
      matched: matched.has(concept),
      gridStyle: { gridRow: row, gridColumn: col },
    }
  })
})

const connectionPaths = ref<{ d: string; visible: boolean }[]>([])

function getBubbleCenter(index: number): { x: number; y: number } | null {
  const el = slotRefs.value[index]
  if (!el) return null
  const rect = el.getBoundingClientRect()
  const wrapper = wrapperRef.value
  if (!wrapper) return null
  const wrapperRect = wrapper.getBoundingClientRect()
  return {
    x: rect.left - wrapperRect.left + rect.width / 2,
    y: rect.top - wrapperRect.top + rect.height / 2,
  }
}

function makeCurvedPath(x1: number, y1: number, x2: number, y2: number): string {
  const mx = (x1 + x2) / 2
  const my = (y1 + y2) / 2
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.sqrt(dx * dx + dy * dy) || 1
  const perpX = -dy / len
  const perpY = dx / len
  const curveOffset = Math.min(len * 0.2, 25)
  const cx = mx + perpX * curveOffset
  const cy = my + perpY * curveOffset
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`
}

function updateConnectionPaths() {
  nextTick(() => {
    if (wrapperRef.value) {
      const rect = wrapperRef.value.getBoundingClientRect()
      wrapperSize.value = { width: rect.width, height: rect.height }
    }
    const paths: { d: string; visible: boolean }[] = []
    const matched = props.matchedConcepts

    for (const [a, b] of CONCEPT_CONNECTIONS) {
      const p1 = getBubbleCenter(a)
      const p2 = getBubbleCenter(b)
      const conceptA = CONCEPT_ORDER[a]
      const conceptB = CONCEPT_ORDER[b]
      const bothMatched = conceptA && conceptB && matched.has(conceptA) && matched.has(conceptB)
      const showLine = isVersion2.value || bothMatched

      if (p1 && p2 && showLine) {
        paths.push({
          d: makeCurvedPath(p1.x, p1.y, p2.x, p2.y),
          visible: isVersion2.value ? true : !!bothMatched,
        })
      }
    }
    connectionPaths.value = paths
  })
}

watch(
  () => [slots.value, props.matchedConcepts],
  () => updateConnectionPaths(),
  { deep: true }
)

watch(
  () => slots.value.some((s) => s.matched),
  () => updateConnectionPaths()
)

watch(
  () => props.matchedConcepts,
  (matched) => {
    const prev = prevMatchedConcepts.value
    const next = new Set(matched)
    const added = [...next].filter((c) => !prev.has(c))
    if (added.length > 0) {
      const nextNewly = new Set(newlyEnteredConcepts.value)
      for (const c of added) nextNewly.add(c)
      newlyEnteredConcepts.value = nextNewly
      setTimeout(() => {
        newlyEnteredConcepts.value = new Set(
          [...newlyEnteredConcepts.value].filter((c) => !added.includes(c))
        )
      }, ENTER_ANIMATION_DURATION)
    }
    prevMatchedConcepts.value = new Set(next)
  },
  { deep: true }
)

let resizeObserver: ResizeObserver | null = null
let observedEl: HTMLElement | null = null
watch(
  () => props.phenomenon,
  () => fetchConceptExplanations(),
  { immediate: true }
)

onMounted(() => {
  loadAppConfig()
  fetchConceptExplanations()
  nextTick(() => {
    setTimeout(updateConnectionPaths, 150)
    observedEl = wrapperRef.value
    if (observedEl) {
      resizeObserver = new ResizeObserver(() => updateConnectionPaths())
      resizeObserver.observe(observedEl)
    }
  })
})
onUnmounted(() => {
  if (resizeObserver && observedEl) {
    resizeObserver.unobserve(observedEl)
  }
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@700;800&display=swap');

.concept-bubbles-wrapper {
  position: relative;
  margin-top: 12px;
  padding: 0 8px;
  max-width: 580px;
  margin-left: auto;
  margin-right: auto;
}

.connection-lines {
  position: absolute;
  top: 0;
  left: 8px;
  width: calc(100% - 20px);
  height: 100%;
  pointer-events: none;
  z-index: 0;
}

.connection-path {
  fill: none;
  stroke: rgba(147, 197, 253, 0.55);
  stroke-width: 2px;
  stroke-linecap: round;
  opacity: 0;
  transition: opacity 0.4s ease;
}

.connection-path.visible {
  opacity: 1;
  stroke-dasharray: 200;
  stroke-dashoffset: 200;
  animation: draw-line 0.6s ease forwards;
}

@keyframes draw-line {
  to {
    stroke-dashoffset: 0;
  }
}

.concept-bubbles {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  grid-template-rows: repeat(3, auto);
  gap: 8px 12px;
  min-height: 320px;
}

.bubble-slot {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  min-height: 80px;
}

.bubble-placeholder {
  width: 72px;
  height: 72px;
  min-width: 72px;
  min-height: 72px;
  visibility: hidden;
  pointer-events: none;
}

.concept-bubble-gray {
  background: radial-gradient(
      circle at 50% 50%,
      rgba(255, 255, 255, 0.4) 0%,
      rgba(255, 255, 255, 0.2) 28%,
      transparent 70%
    ),
    conic-gradient(
      from 0deg,
      rgba(180, 180, 180, 0.4) 0deg,
      rgba(160, 160, 160, 0.4) 120deg,
      rgba(170, 170, 170, 0.4) 240deg,
      rgba(180, 180, 180, 0.4) 360deg
    );
  box-shadow: 0 0 8px rgba(120, 120, 120, 0.3);
  border: 1px solid rgba(150, 150, 150, 0.5);
  color: transparent;
  animation: none;
}

.concept-bubble {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 96px;
  height: 96px;
  padding: 10px;
  box-sizing: border-box;
  border-radius: 50%;
  font-size: 0.95rem;
  font-weight: 800;
  font-family: 'Nunito', 'Comic Sans MS', sans-serif;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.9);
  line-height: 1.2;
  text-align: center;
  word-break: break-word;
  white-space: normal;
  background: radial-gradient(
      circle at 50% 50%,
      white 0%,
      white 28%,
      transparent 70%
    ),
    conic-gradient(
      from 0deg,
      rgba(255, 182, 193, 0.55) 0deg,
      rgba(173, 216, 255, 0.55) 120deg,
      rgba(144, 238, 224, 0.55) 240deg,
      rgba(255, 182, 193, 0.55) 360deg
    );
  box-shadow:
    0 0 16px rgba(173, 216, 255, 0.4),
    0 0 24px rgba(144, 238, 224, 0.25),
    0 0 12px rgba(255, 182, 193, 0.2),
    inset 0 0 12px rgba(255, 255, 255, 0.7),
    inset 2px 2px 8px rgba(255, 182, 193, 0.25),
    inset -2px -2px 8px rgba(173, 216, 255, 0.25),
    inset 0 4px 8px rgba(144, 238, 224, 0.2);
  border: 1px solid rgba(200, 220, 255, 0.6);
  color: #1e40af;
  transition: all 0.3s ease;
  animation: bubble-float 3.5s ease-in-out infinite;
}

.concept-bubble:hover {
  box-shadow:
    0 0 20px rgba(173, 216, 255, 0.5),
    0 0 30px rgba(144, 238, 224, 0.35),
    0 0 16px rgba(255, 182, 193, 0.3),
    inset 0 0 14px rgba(255, 255, 255, 0.75),
    inset 2px 2px 10px rgba(255, 182, 193, 0.3),
    inset -2px -2px 10px rgba(173, 216, 255, 0.3),
    inset 0 4px 10px rgba(144, 238, 224, 0.25);
  transform: translateY(-3px) scale(1.05);
  animation: none;
}

.concept-bubble.concept-bubble-enter {
  animation: bubble-enter-glow 1.8s ease-out forwards;
}

@keyframes bubble-enter-glow {
  0% {
    transform: scale(0.85);
    box-shadow:
      0 0 8px rgba(173, 216, 255, 0.3),
      0 0 12px rgba(144, 238, 224, 0.2),
      0 0 0 0 rgba(147, 197, 253, 0.8),
      0 0 0 0 rgba(255, 215, 0, 0.4),
      inset 0 0 12px rgba(255, 255, 255, 0.7);
    opacity: 0.7;
  }
  25% {
    transform: scale(1.08);
    box-shadow:
      0 0 28px rgba(173, 216, 255, 0.7),
      0 0 40px rgba(144, 238, 224, 0.5),
      0 0 0 12px rgba(147, 197, 253, 0.3),
      0 0 0 24px rgba(255, 215, 0, 0.15),
      inset 0 0 14px rgba(255, 255, 255, 0.9);
    opacity: 1;
  }
  50% {
    transform: scale(1.05);
    box-shadow:
      0 0 32px rgba(173, 216, 255, 0.6),
      0 0 48px rgba(144, 238, 224, 0.4),
      0 0 0 8px rgba(147, 197, 253, 0.2),
      0 0 0 16px rgba(255, 215, 0, 0.08),
      inset 0 0 14px rgba(255, 255, 255, 0.85);
  }
  100% {
    transform: scale(1);
    box-shadow:
      0 0 16px rgba(173, 216, 255, 0.4),
      0 0 24px rgba(144, 238, 224, 0.25),
      0 0 12px rgba(255, 182, 193, 0.2),
      inset 0 0 12px rgba(255, 255, 255, 0.7),
      inset 2px 2px 8px rgba(255, 182, 193, 0.25),
      inset -2px -2px 8px rgba(173, 216, 255, 0.25),
      inset 0 4px 8px rgba(144, 238, 224, 0.2);
    opacity: 1;
  }
}

@keyframes bubble-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
</style>

<style>
/* Tooltip - global so it can escape scoped wrapper and position fixed works */
.concept-tooltip {
  position: fixed;
  z-index: 9999;
  max-width: 320px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.98);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(200, 220, 255, 0.6);
  font-family: 'Comic Sans MS', cursive, sans-serif;
  pointer-events: none;
  line-height: 1.5;
}
.concept-tooltip-title {
  font-weight: 600;
  color: #1e40af;
  font-size: 0.9rem;
  margin-bottom: 6px;
}
.concept-tooltip-body {
  font-size: 0.82rem;
  color: #334155;
}
</style>
