<template>
  <!-- Magnifiers sit near the top, so wide screens crop mostly from the bottom -->
  <FigmaStage v-if="config" :crop-top="0.25">
    <template #default="{ visible }">
      <img class="scene" :src="config.scene.src" :style="rectStyle(config.scene.rect)" alt="" />

      <template v-if="ready && !narrating">
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
        <!-- Every room keeps its magnifier: completion is shown only for whole
             areas, on the map -->
        <button
          v-for="p in rooms"
          :key="`mag-${p.id}`"
          class="magnifier"
          :class="{ active: hovered === p.id }"
          :style="markerStyle(p, visible)"
          :aria-label="`Explore the ${p.label}`"
          @mouseenter="hovered = p.id"
          @mouseleave="hovered = null"
          @click="enterRoom(p.id)"
        >
          <img src="/imgs/ui/magnifier-bubble.png" alt="" />
        </button>
      </template>
    </template>

    <template #overlay>
      <button
        v-if="ready && !narrating"
        class="back-to-map"
        aria-label="Back to map"
        @click="router.push(mapPath)"
      >
        <img class="default" src="/imgs/ui/back-to-map-button.png" alt="" />
        <img class="hover" src="/imgs/ui/back-to-map-button-hover.png" alt="" />
      </button>
      <button
        v-if="ready && !narrating"
        class="finish-exploring"
        :aria-label="`Finish exploring the ${config.label}`"
        :disabled="finishing"
        @click="finish"
      >
        <img class="default" src="/imgs/ui/finish-exploring-button.png" alt="" />
        <img class="hover" src="/imgs/ui/finish-exploring-button-hover.png" alt="" />
      </button>
      <div v-if="narrating" class="wash" />
      <NarrativeBubble v-if="narrating" :lines="config.intro" @done="finishIntro" />
    </template>
  </FigmaStage>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FigmaStage from '../components/FigmaStage.vue'
import NarrativeBubble from '../components/NarrativeBubble.vue'
import { AREAS, phenomenaInArea, type Area, type Phenomenon } from '../constants/phenomena'
import { useAppVersion } from '../utils/appVersion'
import { endActivity, fetchProgress, finishArea } from '../utils/session'
import { rectStyle, introPlayed, markIntroPlayed } from '../utils/stage'

const route = useRoute()
const router = useRouter()
const { version, mapPath, donePath, roomPath, introKey: versionedKey } = useAppVersion()

const area = computed(() => route.params.area as Area)
const config = computed(() => AREAS[area.value])
const rooms = computed(() => phenomenaInArea(area.value))

const hovered = ref<string | null>(null)
/** Rooms the child has explored here (progress), only used to skip the intro */
const explored = ref<string[]>([])

// Magnifier size (85% of its first size, 163×136). It keeps the old magnifier's
// bottom-left corner (120×124 at p.magnifier in Figma), so the tail still points
// at the room.
const MAGNIFIER = { w: 139, h: 116 }
const EDGE = 12
type Bounds = { left: number; top: number; right: number; bottom: number }

// Pulled back inside the window when the cover crop would cut a marker off
const markerStyle = (p: Phenomenon, visible: Bounds) => {
  const size = MAGNIFIER
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

// Nova introduces an area only on the child's first visit: not when they come
// back from a room, and not on a later visit once they have explored a room here
// (progress is per child, so this also holds in a new tab or a second session)
const ready = ref(false)
const narrating = ref(false)

const introKey = computed(() => versionedKey(`area:${area.value}`))

watch(
  area,
  async a => {
    if (!AREAS[a]) {
      router.replace(mapPath.value)
      return
    }
    ready.value = false
    narrating.value = false
    const progress = await fetchProgress(version.value)
    if (area.value !== a) return
    explored.value = progress[a]?.explored ?? []
    narrating.value = !introPlayed(introKey.value) && !explored.value.length
    // Counted as heard once it starts, so leaving mid-intro doesn't replay it
    if (narrating.value) markIntroPlayed(introKey.value)
    ready.value = true
  },
  { immediate: true }
)

const finishIntro = () => {
  narrating.value = false
}

const enterRoom = (id: string) => {
  router.push(roomPath(area.value, id))
}

// Finishing is the completion signal for the area (no confirmation, available any
// time) and ends today's activity: Nova says goodbye and nothing is clickable.
// The map's "welcome back" lines are for the next session.
const finishing = ref(false)
const finish = async () => {
  if (finishing.value) return
  finishing.value = true
  if (!(await finishArea(area.value, version.value))) {
    console.error(`Could not record ${area.value} as finished`)
  }
  endActivity(donePath.value)
  router.replace(donePath.value)
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

/* "Finish Exploring" button, bottom-right of frames 02 / 06. The exported art has
   wide transparent margins, so the button box is the pill (art bbox 142,60 → 965,315
   of 1085×394, shown at the same width as Back to Map) and the image overhangs it. */
.finish-exploring {
  --art-scale: 0.3196;
  position: absolute;
  right: 52px;
  bottom: 28px;
  width: calc(823px * var(--art-scale));
  height: calc(255px * var(--art-scale));
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.finish-exploring img {
  position: absolute;
  left: calc(-142px * var(--art-scale));
  top: calc(-60px * var(--art-scale));
  width: calc(1085px * var(--art-scale));
  height: calc(394px * var(--art-scale));
  max-width: none;
  pointer-events: none;
}

.finish-exploring .hover,
.finish-exploring:hover .default {
  opacity: 0;
}

.finish-exploring:hover .hover {
  opacity: 1;
}

.finish-exploring:active {
  transform: scale(0.97);
}
</style>
