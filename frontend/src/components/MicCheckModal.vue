<template>
  <div class="mic-check-overlay" role="presentation">
    <div
      class="mic-check-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="mic-check-title"
      aria-describedby="mic-check-desc"
    >
      <h2 id="mic-check-title" class="mic-check-title">Microphone check</h2>
      <p id="mic-check-desc" class="mic-check-desc">
        Please say a few words out loud.
      </p>

      <label class="mic-check-label" for="mic-device-select">Microphone</label>
      <select
        id="mic-device-select"
        v-model="selectedDeviceId"
        class="mic-device-select"
        :disabled="deviceList.length === 0"
        @change="onDeviceChange"
      >
        <option v-if="deviceList.length === 0" value="">Loading devices…</option>
        <option
          v-for="d in deviceList"
          :key="d.deviceId"
          :value="d.deviceId"
        >
          {{ d.label || `Microphone ${d.deviceId.slice(0, 8)}…` }}
        </option>
      </select>

      <div class="mic-meter-wrap" aria-live="polite">
        <div class="mic-meter-track">
          <div
            class="mic-meter-fill"
            :style="{ width: `${Math.min(100, meterPercent)}%` }"
            :class="{ active: voiceDetected }"
          />
        </div>
        <p class="mic-meter-status" :class="{ ok: voiceDetected }">
          {{ statusText }}
        </p>
      </div>

      <p v-if="errorMessage" class="mic-check-error" role="alert">{{ errorMessage }}</p>

      <div class="mic-check-actions">
        <button type="button" class="mic-check-btn secondary" @click="retryPermission">
          Retry access
        </button>
        <button type="button" class="mic-check-btn primary" @click="finish" :disabled="!canContinue">
          Continue
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const PREFERRED_MIC_KEY = 'curio_preferred_mic_device_id'

const emit = defineEmits<{
  (e: 'done'): void
}>()

const deviceList = ref<MediaDeviceInfo[]>([])
const selectedDeviceId = ref('')
const meterPercent = ref(0)
const voiceDetected = ref(false)
const errorMessage = ref('')
const streamRef = ref<MediaStream | null>(null)

let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let rafId: number | null = null
let deviceChangeHandler: (() => void) | null = null

const statusText = computed(() => {
  if (errorMessage.value) return 'Please fix the issue above or try another microphone.'
  if (voiceDetected.value) return 'We hear you! Your microphone is working.'
  return 'Speak now! We are listening for your voice.'
})

/** Allow continue once we have a live stream (permission OK). Voice detection is feedback, not a gate. */
const canContinue = computed(() => !!streamRef.value && streamRef.value.getAudioTracks().length > 0)

const refreshInputDevices = async () => {
  try {
    const all = await navigator.mediaDevices.enumerateDevices()
    const inputs = all.filter((d) => d.kind === 'audioinput')
    deviceList.value = inputs
    if (!selectedDeviceId.value && inputs.length > 0) {
      const stored = localStorage.getItem(PREFERRED_MIC_KEY)
      const matchStored = stored && inputs.some((d) => d.deviceId === stored)
      selectedDeviceId.value = matchStored ? stored! : inputs[0]!.deviceId
    } else if (selectedDeviceId.value && !inputs.some((d) => d.deviceId === selectedDeviceId.value)) {
      selectedDeviceId.value = inputs[0]?.deviceId ?? ''
    }
  } catch (e) {
    console.error('enumerateDevices failed:', e)
  }
}

const stopMeter = () => {
  if (rafId != null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  if (sourceNode) {
    try {
      sourceNode.disconnect()
    } catch {
      /* ignore */
    }
    sourceNode = null
  }
  if (analyser) {
    try {
      analyser.disconnect()
    } catch {
      /* ignore */
    }
    analyser = null
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close().catch(() => {})
    audioContext = null
  }
}

const stopStream = () => {
  stopMeter()
  if (streamRef.value) {
    streamRef.value.getTracks().forEach((t) => t.stop())
    streamRef.value = null
  }
}

const startMeter = (stream: MediaStream) => {
  stopMeter()
  const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  audioContext = new AC()
  analyser = audioContext.createAnalyser()
  analyser.fftSize = 512
  analyser.smoothingTimeConstant = 0.65
  sourceNode = audioContext.createMediaStreamSource(stream)
  sourceNode.connect(analyser)

  const data = new Uint8Array(analyser.frequencyBinCount)
  /** Hysteresis: “hearing you” only while level stays up; drops when quiet (e.g. after switching mic). */
  const LEVEL_SPEAK = 10
  const LEVEL_SILENT = 6
  const tick = () => {
    if (!analyser) return
    analyser.getByteFrequencyData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i] ?? 0
    const avg = sum / data.length
    const pct = (avg / 255) * 100 * 2.2
    meterPercent.value = Math.min(100, pct)
    if (avg >= LEVEL_SPEAK) voiceDetected.value = true
    else if (avg <= LEVEL_SILENT) voiceDetected.value = false
    rafId = requestAnimationFrame(tick)
  }
  rafId = requestAnimationFrame(tick)
}

const attachStream = async (constraints: MediaStreamConstraints) => {
  errorMessage.value = ''
  voiceDetected.value = false
  meterPercent.value = 0
  stopStream()
  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints)
    streamRef.value = stream
    await refreshInputDevices()
    startMeter(stream)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    errorMessage.value = `Could not use the microphone: ${msg}. Check browser permissions or pick another device.`
    console.error('getUserMedia failed:', e)
  }
}

const openMic = async () => {
  const id = selectedDeviceId.value
  const audio: MediaTrackConstraints | boolean = id
    ? { deviceId: { exact: id }, echoCancellation: true, noiseSuppression: true }
    : { echoCancellation: true, noiseSuppression: true }
  await attachStream({ audio })
}

const onDeviceChange = async () => {
  if (!selectedDeviceId.value) return
  localStorage.setItem(PREFERRED_MIC_KEY, selectedDeviceId.value)
  await openMic()
}

const retryPermission = async () => {
  voiceDetected.value = false
  meterPercent.value = 0
  await refreshInputDevices()
  await openMic()
}

const finish = () => {
  if (selectedDeviceId.value) {
    localStorage.setItem(PREFERRED_MIC_KEY, selectedDeviceId.value)
  }
  stopStream()
  emit('done')
}

onMounted(async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    errorMessage.value = 'This browser does not support microphone access.'
    return
  }
  deviceChangeHandler = () => {
    void refreshInputDevices()
  }
  navigator.mediaDevices.addEventListener('devicechange', deviceChangeHandler)
  await refreshInputDevices()
  await openMic()
})

onUnmounted(() => {
  if (deviceChangeHandler) {
    navigator.mediaDevices.removeEventListener('devicechange', deviceChangeHandler)
    deviceChangeHandler = null
  }
  stopStream()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Kodchasan:wght@500;600;700&display=swap');

.mic-check-overlay {
  position: fixed;
  inset: 0;
  z-index: 12500;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
  animation: fadeIn 0.25s ease;
}

.mic-check-dialog {
  width: min(440px, 100%);
  background: #ffffff;
  border: 4px solid #bfe4f0;
  border-radius: 24px;
  box-shadow: 0 15px 50px rgba(0, 0, 0, 0.2);
  padding: 24px 22px 20px;
  animation: slideUp 0.25s ease;
}

.mic-check-title {
  margin: 0 0 10px;
  font-family: 'Krona One', sans-serif;
  font-size: clamp(1.1rem, 3.5vw, 1.35rem);
  font-weight: 400;
  color: #3d576a;
  line-height: 1.25;
}

.mic-check-desc {
  margin: 0 0 16px;
  font-family: 'Kodchasan', system-ui, sans-serif;
  font-size: 0.98rem;
  font-weight: 500;
  color: #486174;
  line-height: 1.45;
}

.mic-check-label {
  display: block;
  font-family: 'Kodchasan', system-ui, sans-serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #3d576a;
  margin-bottom: 6px;
}

.mic-device-select {
  width: 100%;
  box-sizing: border-box;
  font-family: 'Kodchasan', system-ui, sans-serif;
  font-size: 0.95rem;
  padding: 10px 12px;
  border-radius: 12px;
  border: 2px solid #b9e0ea;
  background: #fafafa;
  color: #364b5c;
  margin-bottom: 18px;
}

.mic-meter-wrap {
  margin-bottom: 14px;
}

.mic-meter-track {
  height: 14px;
  border-radius: 999px;
  background: #e8f1f4;
  overflow: hidden;
  border: 1px solid rgba(61, 87, 106, 0.12);
}

.mic-meter-fill {
  height: 100%;
  width: 0%;
  border-radius: 999px;
  background: linear-gradient(90deg, #79aaff, #5a8fd9);
  transition: width 0.06s ease-out;
}

.mic-meter-fill.active {
  background: linear-gradient(90deg, #4caf50, #2e7d32);
}

.mic-meter-status {
  margin: 8px 0 0;
  font-family: 'Kodchasan', system-ui, sans-serif;
  font-size: 0.88rem;
  font-weight: 600;
  color: #6b8294;
}

.mic-meter-status.ok {
  color: #2e7d32;
}

.mic-check-error {
  margin: 0 0 12px;
  font-family: 'Kodchasan', system-ui, sans-serif;
  font-size: 0.85rem;
  color: #b00020;
  line-height: 1.4;
}

.mic-check-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 4px;
}

.mic-check-btn {
  font-family: 'Kodchasan', system-ui, sans-serif;
  font-size: 1rem;
  font-weight: 700;
  padding: 10px 18px;
  border-radius: 999px;
  cursor: pointer;
  border: 2px solid #79aaff;
  transition: background 0.15s ease, transform 0.15s ease, opacity 0.15s ease;
}

.mic-check-btn.primary {
  background: #79aaff;
  color: #ffffff;
}

.mic-check-btn.primary:hover:not(:disabled) {
  filter: brightness(1.05);
  transform: scale(1.02);
}

.mic-check-btn.primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.mic-check-btn.secondary {
  background: #ffffff;
  color: #364b5c;
}

.mic-check-btn.secondary:hover {
  background: #e8f4f8;
  transform: scale(1.02);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    transform: translateY(16px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>

<style>
@font-face {
  font-family: 'Krona One';
  src: url('../assets/fonts/KronaOne-Regular.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
</style>
