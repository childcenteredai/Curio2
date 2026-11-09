<template>
  <!-- Continues a picture that can't cover the window: mirrored copies at its edges -->
  <TransitionGroup name="crossfade">
    <img
      v-for="tile in mirrorTiles"
      :key="`${layout.background.src}:${tile.side}`"
      class="layer mirror"
      :class="{ glide }"
      :src="layout.background.src"
      :style="[rectStyle(tile.rect), tile.style]"
      alt=""
    />
  </TransitionGroup>
  <!-- Same image in both layouts glides between them; a different image crossfades -->
  <Transition name="crossfade">
    <img
      :key="layout.background.src"
      class="layer"
      :class="{ glide }"
      :src="layout.background.src"
      :style="rectStyle(layout.background.rect)"
      alt=""
    />
  </Transition>
  <div
    v-if="layout.wash"
    class="layer wash"
    :class="{ glide }"
    :style="[rectStyle(layout.wash), layout.washColor ? { background: layout.washColor } : {}]"
  />
  <img
    v-if="layout.characters"
    class="layer characters"
    :class="{ glide }"
    :src="layout.characters.src"
    :style="rectStyle(layout.characters.rect)"
    :alt="alt"
  />
  <img
    v-if="layout.icon"
    class="layer icon"
    :class="{ glide }"
    :src="layout.icon.src"
    :style="rectStyle(layout.icon.rect)"
    alt=""
  />
</template>

<script setup lang="ts">
/**
 * A room's illustration in a FigmaStage scene slot. Switching `layout` (e.g. the
 * full-screen intro to the chat or explanation frame) animates every layer.
 */
import { computed } from 'vue'
import type { Rect, SceneLayout } from '../constants/phenomena'
import { rectStyle } from '../utils/stage'

const props = withDefaults(
  defineProps<{
    layout: SceneLayout
    /** Describes the characters for screen readers */
    alt?: string
    /** Animate layout changes (off while a layout just follows the window size) */
    glide?: boolean
  }>(),
  { glide: true }
)

/** How far (px) the mirrored continuation takes to tone down to its palest */
const TONE_DOWN = 200
/** Overlap (px) between the picture and its mirrored continuation */
const SEAM = 2

/** Mask that keeps a tile solid at the picture's edge (`dirs` point away from it) and lets the cream page through further out */
const toneDown = (dirs: string[]) => {
  const mask = dirs
    .map(d => `linear-gradient(${d}, #000, rgba(0, 0, 0, 0.55) ${TONE_DOWN}px)`)
    .join(', ')
  return {
    maskImage: mask,
    maskComposite: 'intersect',
    WebkitMaskImage: mask,
    WebkitMaskComposite: 'source-in'
  }
}

/**
 * Mirrored copies beside each edge to continue, plus the corners between two of
 * them. A mirror lines up pixel for pixel with the picture's edge, so the seam is
 * invisible; in the tile's own (unflipped) coordinates that edge is on the same
 * side as the picture edge it continues.
 */
const mirrorTiles = computed(() => {
  const ext = props.layout.extend
  if (!ext) return []
  const [x, y, w, h] = props.layout.background.rect
  const [top, right, bottom, left] = ext
  const tiles: Array<{ side: string; rect: Rect; style: Record<string, string> }> = []
  const add = (side: string, dx: number, dy: number) => {
    const dirs: string[] = []
    if (dx < 0) dirs.push('to right')
    if (dx > 0) dirs.push('to left')
    if (dy < 0) dirs.push('to bottom')
    if (dy > 0) dirs.push('to top')
    tiles.push({
      side,
      // Tucked SEAM px under the picture so sub-pixel rounding leaves no hairline
      rect: [x + dx * (w - SEAM), y + dy * (h - SEAM), w, h],
      style: { transform: `scale(${dx ? -1 : 1}, ${dy ? -1 : 1})`, ...toneDown(dirs) }
    })
  }
  if (top) add('top', 0, -1)
  if (right) add('right', 1, 0)
  if (bottom) add('bottom', 0, 1)
  if (left) add('left', -1, 0)
  if (top && left) add('top-left', -1, -1)
  if (top && right) add('top-right', 1, -1)
  if (bottom && left) add('bottom-left', -1, 1)
  if (bottom && right) add('bottom-right', 1, 1)
  return tiles
})
</script>

<style scoped>
.layer {
  position: absolute;
  object-fit: cover;
}

/* Opacity included so a crossfading image still fades while it glides */
.layer.glide {
  transition: left 0.9s ease, top 0.9s ease, width 0.9s ease, height 0.9s ease, opacity 0.8s ease;
}

/* Softened so the continuation reads as background, not part of the scene */
.mirror {
  filter: saturate(0.8);
}

.characters,
.icon {
  object-fit: contain;
}

.wash {
  background: rgba(255, 249, 239, 0.4);
}

.icon {
  animation: wobble 1.8s ease-in-out infinite;
}

@keyframes wobble {
  50% { transform: rotate(-6deg) scale(1.04); }
}

.crossfade-enter-active,
.crossfade-leave-active {
  transition: opacity 0.8s ease;
}

.crossfade-enter-from,
.crossfade-leave-to {
  opacity: 0;
}
</style>
