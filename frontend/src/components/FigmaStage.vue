<template>
  <div ref="viewport" class="stage-viewport">
    <!-- Scene: covers the whole window (no letterboxing); edges are cropped instead -->
    <div class="stage" :class="{ gliding }" :style="sceneStyle">
      <slot :visible="visible" />
    </div>
    <!-- UI: always fully visible, pinned to the window edges -->
    <div class="overlay" :style="overlayStyle">
      <slot name="overlay" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Two layers sized in Figma pixels.
 *
 * Default slot = the scene (backgrounds, characters, hotspots). It is scaled to
 * cover the window, so artwork always fills the screen and hotspots stay on top
 * of what they belong to.
 *
 * "overlay" slot = UI chrome (Nova's bubble, buttons, chat panel). It is scaled to
 * fit, never cropped, and its box spans the whole window, so children anchor to
 * the window edges with left/right/top/bottom in Figma pixels.
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { GLIDE_MS } from '../utils/stage'

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
    /** Which side of the scene to keep when the window is narrower than the frame */
    align?: 'center' | 'left'
    /**
     * Share of the vertical overflow cropped from the top when the window is wider
     * than the frame (0 = keep the top, 0.5 = crop evenly, 1 = keep the bottom)
     */
    cropTop?: number
  }>(),
  { width: 1463, height: 823, align: 'center', cropTop: 0.5 }
)

const viewport = ref<HTMLElement>()
const vw = ref(props.width)
const vh = ref(props.height)
let observer: ResizeObserver | null = null

// Animate the scene only when switching alignment (intro -> chat), not on resize
const gliding = ref(false)
let glideTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => props.align,
  () => {
    gliding.value = true
    if (glideTimer) clearTimeout(glideTimer)
    glideTimer = setTimeout(() => { gliding.value = false }, GLIDE_MS + 100)
  }
)

const fit = () => {
  const el = viewport.value
  if (!el) return
  vw.value = el.clientWidth
  vh.value = el.clientHeight
}

const scene = computed(() => {
  const s = Math.max(vw.value / props.width, vh.value / props.height)
  const extraX = vw.value - props.width * s // <= 0 when cropping horizontally
  const x = props.align === 'left' ? 0 : extraX / 2
  const y = (vh.value - props.height * s) * props.cropTop
  return { s, x, y }
})

const sceneStyle = computed(() => ({
  width: `${props.width}px`,
  height: `${props.height}px`,
  transform: `translate(${scene.value.x}px, ${scene.value.y}px) scale(${scene.value.s})`
}))

/** Part of the frame actually on screen, in Figma pixels (exposed to the scene slot) */
const visible = computed(() => {
  const { s, x, y } = scene.value
  return { left: -x / s, top: -y / s, right: (vw.value - x) / s, bottom: (vh.value - y) / s }
})

const overlayStyle = computed(() => {
  const s = Math.min(vw.value / props.width, vh.value / props.height)
  return {
    width: `${vw.value / s}px`,
    height: `${vh.value / s}px`,
    transform: `scale(${s})`
  }
})

onMounted(() => {
  fit()
  observer = new ResizeObserver(fit)
  if (viewport.value) observer.observe(viewport.value)
})

onUnmounted(() => {
  observer?.disconnect()
  if (glideTimer) clearTimeout(glideTimer)
})
</script>

<style scoped>
.stage-viewport {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: var(--curio-cream);
}

.stage,
.overlay {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
}

.stage.gliding {
  transition: transform var(--curio-glide) ease;
}

/* Let clicks fall through to the scene except where overlay content sits */
.overlay {
  pointer-events: none;
}

.overlay > :deep(*) {
  pointer-events: auto;
}
</style>
