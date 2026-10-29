<template>
  <FigmaStage v-if="phenomenon" :align="phase === 'chat' ? 'left' : 'center'">
    <!-- Same image in both phases (house) glides; a different chat image (garden) crossfades -->
    <Transition name="crossfade">
      <img
        :key="layout.background.src"
        class="layer"
        :src="layout.background.src"
        :style="rectStyle(layout.background.rect)"
        alt=""
      />
    </Transition>
    <div v-if="layout.wash" class="layer wash" :style="rectStyle(layout.wash)" />
    <img
      v-if="layout.characters"
      class="layer characters"
      :src="layout.characters.src"
      :style="rectStyle(layout.characters.rect)"
      :alt="phenomenon.label"
    />
    <img
      v-if="layout.icon"
      class="layer icon"
      :src="layout.icon.src"
      :style="rectStyle(layout.icon.rect)"
      alt=""
    />

    <template #overlay>
      <Transition name="pop">
        <button
          v-if="phase === 'chat'"
          class="back-to-area"
          :aria-label="`Back to the ${area.label}`"
          @click="router.push(`/area/${area.id}`)"
        >
          <img :src="area.backButton" alt="" />
        </button>
      </Transition>

      <Transition name="slide">
        <div v-if="phase === 'chat' && micCheckComplete" class="chat-panel">
          <Conversation
            :key="phenomenon.id"
            :selectedImagePath="imagePath"
            :phenomenonId="phenomenon.id"
          />
        </div>
      </Transition>
    </template>
  </FigmaStage>
  <MicCheckModal v-if="phase === 'chat' && !micCheckComplete" @done="handleMicCheckDone" />
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FigmaStage from '../components/FigmaStage.vue'
import Conversation from '../components/Conversation.vue'
import MicCheckModal from '../components/MicCheckModal.vue'
import { AREAS, PHENOMENA } from '../constants/phenomena'
import { MIC_CHECK_SESSION_KEY } from '../utils/session'
import { rectStyle, introPlayed, markIntroPlayed } from '../utils/stage'

/** How long the illustration is shown on its own before the chat pops up */
const INTRO_MS = 2500

const route = useRoute()
const router = useRouter()

const phenomenon = computed(() => {
  const p = PHENOMENA[route.params.phenomenon as string]
  return p && p.area === route.params.area ? p : undefined
})
const area = computed(() => AREAS[phenomenon.value?.area ?? 'house'])
// Stable per-room path; the backend keys conversation history on it
const imagePath = computed(() => {
  const intro = phenomenon.value!.intro
  return (intro.characters ?? intro.background).src
})

const phase = ref<'intro' | 'chat'>('intro')
const layout = computed(() => phenomenon.value![phase.value])

const micCheckComplete = ref(sessionStorage.getItem(MIC_CHECK_SESSION_KEY) === '1')
const handleMicCheckDone = () => {
  sessionStorage.setItem(MIC_CHECK_SESSION_KEY, '1')
  micCheckComplete.value = true
}

let timer: ReturnType<typeof setTimeout> | null = null

watch(
  phenomenon,
  p => {
    if (timer) clearTimeout(timer)
    if (!p) {
      router.replace('/')
      return
    }
    const key = `room:${p.id}`
    if (introPlayed(key)) {
      phase.value = 'chat'
      return
    }
    phase.value = 'intro'
    timer = setTimeout(() => {
      markIntroPlayed(key)
      phase.value = 'chat'
    }, INTRO_MS)
  },
  { immediate: true }
)

onUnmounted(() => {
  if (timer) clearTimeout(timer)
})
</script>

<style scoped>
/* Layers glide from the full-screen intro frame to the chat frame */
.layer {
  position: absolute;
  object-fit: cover;
  transition: left 0.9s ease, top 0.9s ease, width 0.9s ease, height 0.9s ease;
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

/* "Room Selection Button" / "outdoor button" instances */
.back-to-area {
  position: absolute;
  left: 28px;
  top: 32px;
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

/* Pinned to the right edge and vertically centred; grows a little on taller
   screens so the conversation has room, but never past the Figma proportions */
.chat-panel {
  position: absolute;
  right: 53px;
  top: 0;
  bottom: 0;
  margin: auto 0;
  width: 528px;
  height: min(calc(100% - 124px), 820px);
}

.crossfade-enter-active,
.crossfade-leave-active {
  transition: opacity 0.8s ease;
}

.crossfade-enter-from,
.crossfade-leave-to {
  opacity: 0;
}

.slide-enter-active {
  transition: transform 0.6s cubic-bezier(0.2, 0.9, 0.3, 1.2), opacity 0.4s ease;
  transition-delay: 0.5s;
}

.slide-enter-from {
  transform: translateX(120px);
  opacity: 0;
}

.pop-enter-active {
  transition: transform 0.4s ease, opacity 0.4s ease;
  transition-delay: 0.6s;
}

.pop-enter-from {
  transform: scale(0.6);
  opacity: 0;
}
</style>
