<template>
  <!-- Magnifiers sit near the top, so wide screens crop mostly from the bottom -->
  <FigmaStage v-if="config" :crop-top="0.25">
    <template #default="{ visible }">
      <img class="scene" :src="config.scene.src" :style="rectStyle(config.scene.rect)" alt="" />

      <template v-if="!narrating">
        <button
          v-for="p in rooms"
          :key="`hit-${p.id}`"
          class="room-hitbox"
          :style="rectStyle(p.hitbox)"
          :aria-label="`Explore the ${p.label}`"
          @mouseenter="hovered = p.id"
          @mouseleave="hovered = null"
          @click="enterRoom(p.id)"
        />
        <!-- Explored rooms show "Done!" instead of the magnifier; both stay clickable -->
        <button
          v-for="p in rooms"
          :key="`mag-${p.id}`"
          class="magnifier"
          :class="{ active: hovered === p.id, done: isExplored(p.id) }"
          :style="markerStyle(p, visible)"
          :aria-label="`${isExplored(p.id) ? 'Explore again' : 'Explore'}: the ${p.label}`"
          @mouseenter="hovered = p.id"
          @mouseleave="hovered = null"
          @click="enterRoom(p.id)"
        >
          <img :src="isExplored(p.id) ? '/imgs/ui/done.png' : '/imgs/ui/magnifier-bubble.png'" alt="" />
        </button>
      </template>
    </template>

    <template #overlay>
      <button
        v-if="!narrating"
        class="back-to-map"
        aria-label="Back to map"
        @click="router.push('/')"
      >
        <img class="default" src="/imgs/ui/back-to-map-button.png" alt="" />
        <img class="hover" src="/imgs/ui/back-to-map-button-hover.png" alt="" />
      </button>
      <div v-if="narrating" class="wash" />
      <NarrativeBubble v-if="narrating" :lines="config.intro" @done="finishIntro" />
    </template>
  </FigmaStage>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FigmaStage from '../components/FigmaStage.vue'
import NarrativeBubble from '../components/NarrativeBubble.vue'
import { AREAS, phenomenaInArea, type Area, type Phenomenon } from '../constants/phenomena'
import { fetchProgress } from '../utils/session'
import { rectStyle, introPlayed, markIntroPlayed } from '../utils/stage'

const route = useRoute()
const router = useRouter()

const area = computed(() => route.params.area as Area)
const config = computed(() => AREAS[area.value])
const rooms = computed(() => phenomenaInArea(area.value))

const hovered = ref<string | null>(null)
const explored = ref<string[]>([])
const isExplored = (id: string) => explored.value.includes(id)

// Marker art sizes. Both bubbles keep the old magnifier's bottom-left corner
// (120×124 at p.magnifier in Figma), so the tail still points at the room.
const MAGNIFIER = { w: 163, h: 136 }
const DONE = { w: 210, h: 174 }
const EDGE = 12
type Bounds = { left: number; top: number; right: number; bottom: number }

// Pulled back inside the window when the cover crop would cut a marker off
const markerStyle = (p: Phenomenon, visible: Bounds) => {
  const size = isExplored(p.id) ? DONE : MAGNIFIER
  const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)
  const left = clamp(p.magnifier[0], visible.left + EDGE, visible.right - size.w - EDGE)
  const top = clamp(p.magnifier[1] + 124 - size.h, visible.top + EDGE, visible.bottom - size.h - EDGE)
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${size.w}px`,
    height: `${size.h}px`
  }
}

onMounted(async () => {
  explored.value = (await fetchProgress())[area.value]?.explored ?? []
})
const narrating = ref(false)

const introKey = computed(() => `area:${area.value}`)

watch(
  area,
  a => {
    if (!AREAS[a]) {
      router.replace('/')
      return
    }
    narrating.value = !introPlayed(introKey.value)
  },
  { immediate: true }
)

const finishIntro = () => {
  markIntroPlayed(introKey.value)
  narrating.value = false
}

const enterRoom = (id: string) => {
  router.push(`/area/${area.value}/${id}`)
}
</script>

<style scoped>
.scene {
  position: absolute;
  object-fit: cover;
}

.wash {
  position: absolute;
  inset: 0;
  background: rgba(255, 249, 239, 0.45);
}

.room-hitbox {
  position: absolute;
  padding: 0;
  border: none;
  border-radius: 18px;
  background: transparent;
  cursor: pointer;
}

.magnifier {
  position: absolute;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  animation: bob 2s ease-in-out infinite;
  transition: transform 0.2s ease;
}

.magnifier img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: transform 0.2s ease, filter 0.2s ease;
}

.magnifier.active img {
  transform: scale(1.15);
  filter: drop-shadow(0 0 12px rgba(255, 211, 77, 0.95));
}

/* Done markers sit still; only rooms left to explore bob for attention */
.magnifier.done {
  animation: none;
}

@keyframes bob {
  50% { transform: translateY(-8px); }
}

/* "Back to map button" instance, frame 02 */
.back-to-map {
  position: absolute;
  left: 11px;
  top: 0;
  width: 289px;
  height: 96px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

.back-to-map img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.back-to-map .hover,
.back-to-map:hover .default {
  opacity: 0;
}

.back-to-map:hover .hover {
  opacity: 1;
}
</style>
