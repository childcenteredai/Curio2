<template>
  <div class="narrative" :class="`layout-${layout}`">
    <img class="nova" :src="novaSrc" alt="Nova" />
    <div class="bubble">
      <div class="name-tag">Nova</div>
      <!-- The whole line is laid out up front (rest kept invisible) so the bubble
           doesn't resize while the text types out -->
      <p class="line" :aria-label="fullLine">
        <span aria-hidden="true">{{ fullLine.slice(0, typed) }}</span
        ><span class="untyped" aria-hidden="true">{{ fullLine.slice(typed) }}</span>
      </p>
      <img
        v-if="current >= 0 && current < lines.length - 1"
        class="next-arrow"
        src="/imgs/ui/narrative-bubble-arrow.svg"
        alt=""
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Nova's scripted narration: one line at a time in the speech bubble,
 * moving on when the synthesized voice for that line finishes.
 * Place it in a FigmaStage's overlay slot (positions are Figma pixels from the window edges).
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { narrate, type Narration } from '../utils/novaVoice'
import { useTypewriter } from '../utils/typewriter'

const props = withDefaults(
  defineProps<{
    lines: string[]
    /** 'map' = waving Nova on the 1463×889 map; 'choose' = thinking Nova on area screens */
    layout?: 'map' | 'choose'
  }>(),
  { layout: 'choose' }
)

const emit = defineEmits<{ (e: 'done'): void }>()

const current = ref(-1)
const { typed, type, finish, stop: stopTyping } = useTypewriter()
const fullLine = computed(() => props.lines[current.value] ?? '')
const novaSrc = computed(() =>
  props.layout === 'map' ? '/imgs/nova/nova-waving.png' : '/imgs/nova/nova-thinking.png'
)

let narration: Narration | null = null

// Typewriter paced to the spoken line: the text finishes just before the voice does
const typeLine = (index: number, durationMs: number) => {
  current.value = index
  type(fullLine.value.length, durationMs)
}

const start = () => {
  narration?.cancel()
  stopTyping()
  current.value = -1
  narration = narrate(props.lines, typeLine, () => {
    finish(fullLine.value.length)
    emit('done')
  })
}

onMounted(start)
watch(() => props.lines, start)
onUnmounted(() => {
  narration?.cancel()
  stopTyping()
})
</script>

<style scoped>
.narrative {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.nova {
  position: absolute;
  object-fit: contain;
}

/* Measured from the Figma renders. The bottom edge is fixed and the box grows
   upward, so a three-line script still fits. */
.bubble {
  position: absolute;
  width: 947px;
  min-height: 152px;
  box-sizing: border-box;
  padding: 26px 64px 24px 33px;
  display: flex;
  align-items: center;
  background: #fcf0d9;
  border: 12px solid #03365f;
  border-radius: 40px;
  box-shadow: 0 6px 0 #03365f;
}

.name-tag {
  position: absolute;
  left: 5px;
  top: -38px;
  width: 223px;
  height: 55px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--curio-lavender);
  border: 5px solid var(--curio-navy);
  border-radius: 16px;
  font-family: var(--curio-font-mono);
  font-weight: 700;
  font-size: 30px;
  color: var(--curio-navy);
}

.line {
  margin: 0;
  font-family: var(--curio-font-mono);
  font-weight: 700;
  font-size: 32px;
  line-height: 1.35;
  color: var(--curio-navy);
  text-align: left;
}

.untyped {
  visibility: hidden;
}

.next-arrow {
  position: absolute;
  right: 22px;
  bottom: 20px;
  width: 42px;
  transform: rotate(90deg);
  opacity: 0.9;
  animation: nudge 1.2s ease-in-out infinite;
}

@keyframes nudge {
  50% { transform: rotate(90deg) translateY(-6px); }
}

/* Positions from frames "00. Map -- Nova intro" and "01C — Choose a room",
   anchored to the bottom-left corner of the window (FigmaStage overlay) */
.layout-map .nova { left: 0; bottom: 14px; width: 382px; height: 382px; }
.layout-map .bubble { left: 355px; bottom: 51px; }

.layout-choose .nova { left: -24px; bottom: 60px; width: 403px; height: 418px; }
.layout-choose .bubble { left: 341px; bottom: 90px; }
</style>
