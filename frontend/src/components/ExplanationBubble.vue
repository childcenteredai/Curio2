<template>
  <div class="explanation">
    <div class="row">
      <!-- Hidden (not removed) on the first bullet so the bubble doesn't shift -->
      <button
        class="arrow prev"
        :class="{ hidden: !canGoBack }"
        :disabled="!canGoBack"
        :tabindex="canGoBack ? 0 : -1"
        aria-label="Go back"
        @click="emit('back')"
      >
        <img src="/imgs/ui/arrow-button-hd.png" alt="" />
      </button>

      <div class="bubble-wrap">
        <div class="bubble">
          <!-- The whole bullet is laid out up front (rest kept invisible) so the
               bubble is its final size before the text types out -->
          <p class="line" :style="lineStyle" :aria-label="text" aria-live="polite">
            <span aria-hidden="true">{{ text.slice(0, typed) }}</span
            ><span class="untyped" aria-hidden="true">{{ text.slice(typed) }}</span>
          </p>
        </div>
        <img class="nova" src="/imgs/nova/nova-peeking-hd.png" alt="Nova" />
      </div>

      <button
        class="arrow next"
        :class="{ beckon: ready }"
        :aria-label="isLast ? 'Finish and go back to the rooms' : 'Next'"
        @click="emit('next')"
      >
        <img src="/imgs/ui/arrow-button-hd.png" alt="" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Nova's explanation bubble (direct-instruction frames 03D/04D/05E/07B-09B):
 * one bullet at a time, with back / next arrows on either side.
 * Place it in a FigmaStage's overlay slot.
 */
import { computed } from 'vue'
import { bubbleLineHeight } from '../utils/explainLayout'

const props = withDefaults(defineProps<{
  text: string
  /** Characters typed so far */
  typed: number
  canGoBack: boolean
  isLast: boolean
  /** Nova has finished this bullet: the next arrow nudges for attention */
  ready: boolean
  /** Text size for this room (Figma px); smaller for rooms with long bullets */
  fontSize?: number
}>(), { fontSize: 30 })

const lineStyle = computed(() => ({
  fontSize: `${props.fontSize}px`,
  lineHeight: `${bubbleLineHeight(props.fontSize)}px`
}))

const emit = defineEmits<{ (e: 'back'): void; (e: 'next'): void }>()
</script>

<style scoped>
.explanation {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

/* Arrows (81px circles), gaps and bubble from the Figma frame: 133 → 1386 on the
   1463 frame. Centred on the window, bottom-anchored, and the bubble grows upward
   for longer bullets with the arrows staying level with its middle.
   The box sizes here are also in BUBBLE (utils/explainLayout.ts), which measures
   bullets to keep the scene clear of the bubble: change both together. */
.row {
  position: absolute;
  left: 50%;
  bottom: 24px;
  margin-left: -598.5px;
  width: 1253px;
  display: flex;
  align-items: center;
}

.bubble-wrap {
  position: relative;
  flex: 0 0 1008px;
  margin: 0 41px 0 42px;
}

.bubble {
  min-height: 160px;
  box-sizing: border-box;
  padding: 16px 24px 16px 53px;
  display: flex;
  align-items: center;
  background: #fcf0d9;
  border: 12px solid #03365f;
  border-radius: 40px;
  box-shadow: 0 6px 0 #03365f;
}

.line {
  margin: 0;
  font-family: var(--curio-font-mono);
  font-weight: 700;
  font-size: 30px;
  line-height: 38px;
  color: var(--curio-navy);
  text-align: left;
}

.untyped {
  visibility: hidden;
}

/* "nova chat 1": 333×222 at (209, 455), i.e. over the bubble's top-left edge */
.nova {
  position: absolute;
  left: -46px;
  top: -184px;
  width: 333px;
  height: 222px;
  pointer-events: none;
}

/* One arrow image (1536×1024 original, transparent margins), mirrored for "back"
   as in Figma. Shown at its Figma size, 163.5×109; the button is just the circle. */
.arrow {
  position: relative;
  flex: 0 0 81px;
  height: 81px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  pointer-events: auto;
  transition: transform 0.15s ease;
}

.arrow img {
  position: absolute;
  top: -14px;
  width: 163.5px;
  height: 109px;
  max-width: none;
  pointer-events: none;
}

.prev img { left: -42px; transform: scaleX(-1); }
.next img { left: -41px; }

.arrow:hover {
  transform: scale(1.08);
}

.arrow:active {
  transform: scale(0.94);
}

.arrow.hidden {
  visibility: hidden;
}

.arrow:focus-visible {
  outline: 5px solid var(--curio-yellow);
  outline-offset: 2px;
}

.next.beckon {
  animation: beckon 1.2s ease-in-out infinite;
}

@keyframes beckon {
  50% { transform: translateX(6px) scale(1.06); }
}
</style>
