<template>
  <div class="chat-container" :class="{ teacher: teacherMode }">
    <header class="chat-panel-header">
      <h1 class="chat-panel-title">ASK NOVA ANYTHING!</h1>
      <!-- Starts this room's chat over in a new conversation (the old one stays in
           the database); only while Nova is quiet and the mic is off -->
      <button
        type="button"
        class="restart-chat-button"
        :disabled="!canRestartChat"
        aria-label="Start this chat over"
        title="Start over"
        @click="restartChat"
      >
        <i class="fa-solid fa-rotate-right" aria-hidden="true" />
      </button>
    </header>

    <!-- Chat messages area -->
    <div 
      class="chat-messages" 
      ref="messagesContainer"
      :class="{ 'scrolled': isScrolled }"
      @scroll="handleScroll"
    >
      
      <div 
        v-for="(msg, index) in chatHistory" 
        :key="index" 
        :class="`message ${msg.role}`"
        v-show="msg.role === 'user' || (msg.role === 'assistant' && msg.audioReady !== false)"
      >
        <div class="message-inner">
          <img
            v-if="msg.role === 'assistant'"
            src="/imgs/nova/nova-avatar-circle.png"
            alt=""
            class="message-avatar"
          >
          <div class="message-bubble">
            <div class="message-text">
              <template v-if="msg.words">
                <span 
                  v-for="(word, wordIndex) in renderWordsWithBoldState(msg.words)" 
                  :key="wordIndex"
                  :class="{ 
                    'word-visible': word.visible, 
                    'word-hidden': !word.visible,
                    'bold-highlight': word.isBold,
                    'bold-first': word.isFirstBold,
                    'bold-last': word.isLastBold
                  }"
                  v-html="escapeHtml(word.text)"
                ></span>
              </template>
              <span v-else v-html="renderTextWithBoldState(msg.content)"></span>
            </div>
            <!-- <div class="message-time">{{ msg.time }}</div> -->
          </div>
        </div>
      </div>
    </div>

    <!-- Teacher version: the mic fills an editable box, and nothing is sent until
         the teacher presses Send (Enter also sends, Shift+Enter is a new line) -->
    <div v-if="teacherMode" class="chat-input-area teacher-input">
      <textarea
        ref="draftBox"
        v-model="draft"
        class="draft-box"
        rows="3"
        :placeholder="isRecording ? 'Listening…' : isTranscribing ? 'Writing it down…' : 'Press the mic and speak, or type here'"
        aria-label="Message to Nova"
        @keydown="handleDraftKeydown"
      ></textarea>
      <div class="teacher-actions">
        <button
          @click="handleVoiceClick"
          :disabled="micLocked"
          :class="`voice-input-button ${isRecording ? 'recording' : ''} ${isTranscribing ? 'loading' : ''}`"
          :aria-label="isRecording ? 'Stop recording' : 'Record'"
          :title="isTranscribing ? 'Writing it down...' : isRecording ? 'Click to stop' : 'Click to speak'"
        >
          <span v-if="isTranscribing" class="voice-loading-face">
            <i class="fa-solid fa-spinner fa-spin loading-icon" aria-hidden="true" />
          </span>
          <img
            v-else
            class="voice-icon"
            :src="isRecording ? '/imgs/ui/mic-button-active.png' : '/imgs/ui/mic-button.png'"
            alt=""
          />
        </button>
        <p class="draft-status" :class="{ warn: transcribeFailed }" aria-live="polite">{{ draftStatus }}</p>
        <button class="send-button" :disabled="!canSend" @click="sendDraft">
          <i v-if="isLoading" class="fa-solid fa-spinner fa-spin" aria-hidden="true" />
          <span v-else>Send</span>
        </button>
      </div>
    </div>

    <!-- Voice input: click to start, click again to send -->
    <div v-else class="chat-input-area">
      <div class="voice-input-container">
        <button 
          @click="handleVoiceClick"
          :disabled="novaBusy"
          :class="`voice-input-button ${isRecording ? 'recording' : ''} ${novaBusy ? 'loading' : ''}`"
          :title="novaBusy ? 'Nova is talking...' : isRecording ? 'Click to send' : 'Click to speak'"
        >
          <!-- While Nova thinks or talks: plain button face with a spinner, no mic -->
          <span v-if="novaBusy" class="voice-loading-face">
            <i class="fa-solid fa-spinner fa-spin loading-icon" aria-hidden="true" />
          </span>
          <img
            v-else
            class="voice-icon"
            :src="isRecording ? '/imgs/ui/mic-button-active.png' : '/imgs/ui/mic-button.png'"
            alt=""
          />
        </button>
      </div>
    </div>

    <!-- 10-min room choice popup -->
    <div
      v-if="showRoomChoicePopup"
      class="room-choice-overlay"
      @click.self.stop
    >
      <div class="room-choice-container popup-card" role="dialog" aria-modal="true" aria-label="Room choice">
        <div class="room-choice-title">Quick Check-in</div>
        <div class="room-choice-question">
          Do you want to explore another room or continue exploring this room?
        </div>
        <div class="room-choice-actions">
          <button class="popup-button secondary" @click="handleExploreAnotherRoom">
            Another room
          </button>
          <button class="popup-button primary" @click="handleContinueThisRoom">
            This room
          </button>
        </div>
      </div>
    </div>

    <!-- 30-min global session reminder (from first app load in this tab) -->
    <div
      v-if="showMissionCompletePopup"
      class="mission-complete-overlay"
      @click.self="handleMissionCompleteDismiss"
    >
      <div class="mission-complete-container popup-card" role="dialog" aria-modal="true" aria-label="Session reminder">
        <img class="happy-nova" src="/imgs/nova/nova-happy.png" alt="" />
        <img class="star star-1" src="/imgs/ui/star.png" alt="" />
        <img class="star star-2" src="/imgs/ui/star.png" alt="" />
        <img class="star star-3" src="/imgs/ui/star.png" alt="" />
        <div class="mission-complete-message">
          Excellent work! We successfully completed our detective mission today. Let's get back to your researcher!
        </div>
        <button type="button" class="popup-button primary" @click="handleMissionCompleteDismiss">
          OK
        </button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { PHENOMENA, phenomenonForImage } from '../constants/phenomena'
import { getOrCreateSessionId } from '../utils/session'
import { atNovaRate } from '../utils/novaVoice'
import { useAppVersion } from '../utils/appVersion'
// Use relative paths - works with nginx reverse proxy (local) and Ingress (prod)

// Props
const props = defineProps<{
  selectedImagePath?: string
  phenomenonId?: string
}>()

const phenomenon = computed(() =>
  (props.phenomenonId && PHENOMENA[props.phenomenonId]) || phenomenonForImage(props.selectedImagePath)
)
// Nova's fixed first line for this room
const openingLine = computed(() =>
  phenomenon.value?.opening ?? "Hi, I'm Nova, your friendly science assistant. What do you find odd in this picture?"
)
// State
const isLoading = ref(false)
const isRecording = ref(false)
const chatHistory = ref<Array<{
  role: string, 
  content: string, 
  time: string,
  words?: Array<{text: string, visible: boolean}>,
  audioReady?: boolean
}>>([])
const messagesContainer = ref<HTMLElement>()
const isScrolled = ref(false)
const convState = ref<'greet' | 'scaffolding' | 'scienceqa_init' | 'scienceqa' | 'reflection' | 'close'>('greet')
const conversationId = ref<string>(crypto.randomUUID())
const sessionId = ref<string>(getOrCreateSessionId())
const isGeneratingGreeting = ref(false)

const router = useRouter()
const { version, mapPath, areaPath } = useAppVersion()
// Teacher version (/teacher): Nova's lines are shown as text only (no speech), and
// the mic fills an editable box that the teacher sends when it's right
const teacherMode = computed(() => version.value === 'teacher')

const isPlayingResponseAudio = ref(false)
// Nova is preparing or speaking a line (greeting or reply): the mic is locked
const novaBusy = computed(
  () => isLoading.value || isGeneratingGreeting.value || isPlayingResponseAudio.value
)

// --- Teacher version input ----------------------------------------------------
const draft = ref('')
const draftBox = ref<HTMLTextAreaElement>()
const isTranscribing = ref(false)
const transcribeFailed = ref(false)
// What speech-to-text produced for the current draft, and the latest recording,
// stored with the message so the edits can be compared later
let draftTranscripts: string[] = []
let draftAudio: { blob: Blob; mimeType: string } | null = null

// Teacher version: recording and editing stay open while Nova replies; only
// sending waits. Question-asking version: the mic is locked while Nova is busy.
const micLocked = computed(() => (teacherMode.value ? isTranscribing.value : novaBusy.value))
const canSend = computed(
  () =>
    draft.value.trim().length > 0 &&
    !isLoading.value &&
    !isGeneratingGreeting.value &&
    !isRecording.value &&
    !isTranscribing.value
)
const draftStatus = computed(() => {
  if (isRecording.value) return 'Listening… press the mic again to stop'
  if (isTranscribing.value) return 'Writing it down…'
  if (transcribeFailed.value) return "Didn't catch that. Try again, or type it."
  if (isLoading.value) return 'Nova is replying…'
  if (draft.value.trim()) return 'Check the text, then send'
  return 'Press the mic to speak'
})

// 10-minute popup: ask whether to explore another room (never while TTS is playing)
const showRoomChoicePopup = ref(false)
const roomChoiceShowPending = ref(false)
let roomChoiceTimeout: ReturnType<typeof setTimeout> | null = null

const tryShowRoomChoicePopup = () => {
  if (isPlayingResponseAudio.value) {
    roomChoiceShowPending.value = true
  } else {
    showRoomChoicePopup.value = true
  }
}

const startRoomChoiceTimer = () => {
  if (roomChoiceTimeout) {
    clearTimeout(roomChoiceTimeout)
    roomChoiceTimeout = null
  }
  roomChoiceShowPending.value = false
  roomChoiceTimeout = setTimeout(() => {
    tryShowRoomChoicePopup()
  }, 10 * 60 * 1000)
}
const handleExploreAnotherRoom = () => {
  showRoomChoicePopup.value = false
  startRoomChoiceTimer() // reset when child re-enters a (new) room
  router.push(phenomenon.value ? areaPath(phenomenon.value.area) : mapPath.value)
}
const handleContinueThisRoom = () => {
  showRoomChoicePopup.value = false
}

// 30-minute reminder: clock starts once when the first chat session begins (first Conversation mount).
// Switching images or starting a new conversation does not reset it.
const GLOBAL_SESSION_START_KEY = 'curio_global_session_start'
const MISSION_COMPLETE_SHOWN_KEY = 'curio_mission_complete_popup_shown'
const MISSION_COMPLETE_MS = 30 * 60 * 1000

/** Anchor the 30-min timer the first time the child enters chat; never overwrite (same tab session). */
const ensureFirstConversationClockAnchor = () => {
  if (!sessionStorage.getItem(GLOBAL_SESSION_START_KEY)) {
    sessionStorage.setItem(GLOBAL_SESSION_START_KEY, String(Date.now()))
  }
}

const showMissionCompletePopup = ref(false)
const missionCompleteShowPending = ref(false)
let missionCompleteTimeout: ReturnType<typeof setTimeout> | null = null

const isMissionCompleteAlreadyShown = () =>
  sessionStorage.getItem(MISSION_COMPLETE_SHOWN_KEY) === '1'

const tryShowMissionCompletePopup = () => {
  if (isMissionCompleteAlreadyShown()) return
  if (isPlayingResponseAudio.value) {
    missionCompleteShowPending.value = true
  } else {
    showMissionCompletePopup.value = true
    sessionStorage.setItem(MISSION_COMPLETE_SHOWN_KEY, '1')
  }
}

const scheduleMissionCompleteTimer = () => {
  if (missionCompleteTimeout) {
    clearTimeout(missionCompleteTimeout)
    missionCompleteTimeout = null
  }
  if (isMissionCompleteAlreadyShown()) return
  const raw = sessionStorage.getItem(GLOBAL_SESSION_START_KEY)
  if (!raw) return
  const startMs = parseInt(raw, 10)
  const elapsed = Date.now() - startMs
  const remaining = MISSION_COMPLETE_MS - elapsed
  if (remaining <= 0) {
    tryShowMissionCompletePopup()
    return
  }
  missionCompleteTimeout = setTimeout(() => {
    tryShowMissionCompletePopup()
  }, remaining)
}

const handleMissionCompleteDismiss = () => {
  showMissionCompletePopup.value = false
}

const PREFERRED_MIC_KEY = 'curio_preferred_mic_device_id'

const buildAudioConstraints = (): MediaTrackConstraints => {
  const id = localStorage.getItem(PREFERRED_MIC_KEY)
  if (id) {
    return {
      deviceId: { exact: id },
      echoCancellation: true,
      noiseSuppression: true
    }
  }
  return { echoCancellation: true, noiseSuppression: true }
}

// Audio recording
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []
// Unused - kept for potential future use with analyzeAudioBlob
// let audioContext: AudioContext | null = null
let recorderMimeType = ''
let currentAudio: HTMLAudioElement | null = null
// Call backend transcription API
const transcribeWithBackend = async (audioBlob: Blob): Promise<string> => {
  const formData = new FormData()
  const ext = audioBlob.type.includes('webm') ? 'webm' :
               audioBlob.type.includes('ogg') ? 'ogg' :
               audioBlob.type.includes('mp3') ? 'mp3' : 'wav'
  formData.append('audio', audioBlob, `recording.${ext}`)

  const resp = await fetch('/api/transcribe', {
    method: 'POST',
    body: formData
  })

  if (!resp.ok) {
    const errText = await resp.text().catch(() => '')
    throw new Error(`Transcription failed: ${resp.status} ${errText}`)
  }

  const json = await resp.json()
  return json.text as string
}

// Analyze audio to detect invalid inputs (too short, tiny size, near-silence)
// Unused function - kept for potential future use
// const analyzeAudioBlob = async (audioBlob: Blob): Promise<{ durationSec: number; peak: number; rms: number }> => {
//   if (!audioContext) {
//     audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
//   }
//   const arrayBuf = await audioBlob.arrayBuffer()
//   const audioBuf = await audioContext.decodeAudioData(arrayBuf)
//   const channelData = audioBuf.getChannelData(0)
//   let peak = 0
//   let sumSquares = 0
//   for (let i = 0; i < channelData.length; i++) {
//     const v = channelData[i] ?? 0
//     const av = Math.abs(v)
//     if (av > peak) peak = av
//     sumSquares += v * v
//   }
//   const rms = Math.sqrt(sumSquares / channelData.length)
//   return { durationSec: audioBuf.duration ?? 0, peak, rms }
// }

// Unused function - kept for potential future use
// const isInvalidAudio = async (audioBlob: Blob): Promise<boolean> => {
//   // Size heuristic: extremely small payloads are likely invalid
//   if (audioBlob.size < 2000) return true
//   try {
//     const { durationSec, peak, rms } = await analyzeAudioBlob(audioBlob)
//     // Too short
//     if (durationSec < 0.6) return true
//     // Near-silence thresholds (tuned conservatively)
//     if (peak < 0.01 && rms < 0.005) return true
//     return false
//   } catch {
//     // If decoding fails, be conservative and allow transcription
//     return false
//   }
// }

const getCurrentTime = () => {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Helper to escape HTML
const escapeHtml = (str: string): string => {
  if (!str) return ''
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

// Simple bold state tracking: if word contains '**', toggle bold state
/**
 * Highlights are the **…** spans in Nova's replies. A highlight covers only the text
 * inside the markers, and it stops before an em dash: the rest of that span stays
 * plain. `state` carries an open span from one word to the next.
 */
const EM_DASH = '\u2014'
type HighlightState = { open: boolean; cut: boolean }
const highlightRuns = (text: string, state: HighlightState): Array<{ text: string; bold: boolean }> => {
  const runs: Array<{ text: string; bold: boolean }> = []
  let run = ''
  let runBold = state.open && !state.cut
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '*' && text[i + 1] === '*') {
      i++
      state.open = !state.open
      state.cut = false
      continue
    }
    if (text[i] === EM_DASH && state.open) state.cut = true
    const bold = state.open && !state.cut
    if (bold !== runBold && run) {
      runs.push({ text: run, bold: runBold })
      run = ''
    }
    runBold = bold
    run += text[i]
  }
  if (run) runs.push({ text: run, bold: runBold })
  return runs
}

type RenderedWord = { text: string; visible: boolean; isBold: boolean; isFirstBold?: boolean; isLastBold?: boolean }

// Words of a spoken reply, split where a highlight starts or stops, with the first and
// last piece of each highlighted run marked
const renderWordsWithBoldState = (words: Array<{text: string, visible: boolean}>): RenderedWord[] => {
  if (!words) return []

  const state: HighlightState = { open: false, cut: false }
  const processedWords: RenderedWord[] = []

  for (const word of words) {
    // Whitespace between highlighted words is never highlighted
    if (/^\s+$/.test(word.text)) {
      processedWords.push({ text: word.text, visible: word.visible, isBold: false })
      continue
    }
    for (const run of highlightRuns(word.text, state)) {
      processedWords.push({ text: run.text, visible: word.visible, isBold: run.bold })
    }
  }

  for (let i = 0; i < processedWords.length; i++) {
    const word = processedWords[i]
    if (!word?.isBold) continue
    if (i === 0 || !processedWords[i - 1]?.isBold) word.isFirstBold = true
    if (i === processedWords.length - 1 || !processedWords[i + 1]?.isBold) word.isLastBold = true
  }

  return processedWords
}

// Render text with bold state (for messages without words array)
const renderTextWithBoldState = (text: string): string => {
  if (!text) return ''
  return highlightRuns(text, { open: false, cut: false })
    .map(run => (run.bold ? `<strong class="bold-highlight">${escapeHtml(run.text)}</strong>` : escapeHtml(run.text)))
    .join('')
}


const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
  updateScrollState()
}

const handleScroll = () => {
  updateScrollState()
}

const updateScrollState = () => {
  if (messagesContainer.value) {
    const container = messagesContainer.value
    const scrollTop = container.scrollTop
    
    // Find all message elements
    const messages = container.querySelectorAll('.message')
    
    if (messages.length === 0) {
      isScrolled.value = false
      return
    }
    
    // Find the first message that's currently visible in the viewport
    let firstVisibleMessage: HTMLElement | null = null
    const containerRect = container.getBoundingClientRect()
    
    for (let i = 0; i < messages.length; i++) {
      const message = messages[i] as HTMLElement
      const messageRect = message.getBoundingClientRect()
      
      // Check if message is visible in viewport (even partially)
      if (messageRect.bottom >= containerRect.top && messageRect.top <= containerRect.bottom) {
        firstVisibleMessage = message
        break
      }
    }
    
    // If no visible message found, check if we've scrolled past all messages
    if (!firstVisibleMessage && messages.length > 0) {
      // If scrollTop > 0, there's content above
      isScrolled.value = scrollTop > 0
      return
    }
    
    if (firstVisibleMessage) {
      // Calculate the distance between container's actual top and message's top
      // offsetTop gives position relative to container's content area
      const messageOffsetTop = firstVisibleMessage.offsetTop
      const distanceFromTop = messageOffsetTop - scrollTop
      
      // Show shadow if there's any gap (message is below the top of viewport)
      // or if we've scrolled down (scrollTop > 0)
      isScrolled.value = distanceFromTop > 0 || scrollTop > 0
    } else {
      isScrolled.value = scrollTop > 0
    }
  }
}

const handleVoiceClick = async () => {
  if (micLocked.value) return
  if (isRecording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: buildAudioConstraints()
    })
    mediaRecorder = new MediaRecorder(stream)
    recorderMimeType = mediaRecorder.mimeType || 'audio/webm'
    audioChunks = []

    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data)
    }

    mediaRecorder.onstop = async () => {
      const blobType = recorderMimeType || mediaRecorder?.mimeType || 'audio/webm'
      const audioBlob = new Blob(audioChunks, { type: blobType })
      await processAudio(audioBlob, blobType)
    }

    mediaRecorder.start()
    isRecording.value = true
  } catch (error) {
    console.error('Error accessing microphone:', error)
  }
}

const stopRecording = () => {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
    isRecording.value = false
  }
}

const blobToBase64 = async (blob: Blob): Promise<string> => {
  const arrayBuffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(arrayBuffer)
  const chunkSize = 0x8000
  let binary = ''
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize)
    binary += String.fromCharCode(...chunk)
  }
  return btoa(binary)
}

// --- Sentence-by-sentence streaming TTS + progressive reveal -----------------
// Instead of waiting for the full response AND full TTS before the child sees or
// hears anything, we detect sentence boundaries in the streaming text, synthesize
// each sentence as soon as it is ready, and play the clips in order while
// revealing the matching words. This makes the first sentence audible within
// ~1-2s of generation starting.

type WordToken = { text: string; visible: boolean }

interface SpeechJob {
  text: string
  wordStart: number
  wordEnd: number
  promise: Promise<Blob>
  abort: AbortController
}

interface PlaybackSession {
  messageIndex: number
  queue: SpeechJob[]
  nextIndex: number
  finished: boolean // producer will not add any more jobs
  cancelled: boolean
  firstStarted: boolean // first clip has begun (bubble revealed)
  wake: (() => void) | null // resolve the player's idle wait when a job arrives
  activeAudio: HTMLAudioElement | null
  activeUrl: string | null
}

let currentPlayback: PlaybackSession | null = null

const MIN_SENTENCE_CHARS = 15

// Pull the leading complete sentence off `pending`, or null if none is ready yet.
// Tiny fragments are merged into the next sentence unless `allowShort` is set
// (used for the very first sentence so time-to-first-audio stays low).
const extractLeadingSentence = (
  pending: string,
  allowShort: boolean
): { sentence: string; rest: string } | null => {
  // A boundary is .!? (optionally followed by closing quotes/brackets) then
  // whitespace or end-of-string. Requiring whitespace/end after avoids splitting
  // decimals like "3.5".
  const re = /[.!?]+[)\]"'”’]*(?=\s|$)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(pending)) !== null) {
    const end = m.index + m[0].length
    const sentence = pending.slice(0, end)
    if (!allowShort && sentence.trim().length < MIN_SENTENCE_CHARS) {
      continue // keep scanning to merge a tiny fragment into a longer chunk
    }
    return { sentence, rest: pending.slice(end) }
  }
  return null
}

const revealWordRange = (pb: PlaybackSession, start: number, end: number) => {
  const msg = chatHistory.value[pb.messageIndex]
  if (!msg || !msg.words) return
  for (let i = start; i < end && i < msg.words.length; i++) {
    const w = msg.words[i]
    if (w) w.visible = true
  }
}

// Append a sentence's word tokens to the message and start its TTS request now,
// so synthesis overlaps ongoing generation / playback of earlier sentences.
const enqueueSentence = (pb: PlaybackSession, rawSentence: string) => {
  const text = rawSentence.trim()
  if (!text) return
  const msg = chatHistory.value[pb.messageIndex]
  if (!msg || !msg.words) return

  const wordStart = msg.words.length
  const tokens: WordToken[] = rawSentence
    .split(/(\s+)/)
    .filter(w => w.length > 0)
    .map(w => ({ text: w, visible: false }))
  msg.words.push(...tokens)
  const wordEnd = msg.words.length

  const abort = new AbortController()
  const promise = fetch('/api/speech', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal: abort.signal
  }).then(async (resp) => {
    if (!resp.ok) throw new Error(`Speech generation failed: ${resp.status}`)
    return await resp.blob()
  })
  promise.catch(() => { /* handled in the player, or aborted on cancel */ })

  pb.queue.push({ text, wordStart, wordEnd, promise, abort })
  pb.wake?.()
}

// Play a single sentence clip, revealing its words in sync with the audio.
const playSentenceClip = (pb: PlaybackSession, job: SpeechJob, blob: Blob): Promise<void> => {
  return new Promise<void>((resolve) => {
    const url = URL.createObjectURL(blob)
    const audio = atNovaRate(new Audio(url))
    pb.activeAudio = audio
    pb.activeUrl = url
    currentAudio = audio // keep legacy stop/cleanup paths working

    let intervalId: ReturnType<typeof setInterval> | null = null
    const clearTimer = () => { if (intervalId) { clearInterval(intervalId); intervalId = null } }

    const cleanup = () => {
      clearTimer()
      if (pb.activeUrl === url) { URL.revokeObjectURL(url); pb.activeUrl = null }
      if (pb.activeAudio === audio) pb.activeAudio = null
      if (currentAudio === audio) currentAudio = null
    }

    const finish = () => {
      revealWordRange(pb, job.wordStart, job.wordEnd)
      scrollToBottom()
      cleanup()
      resolve()
    }

    const startPrinter = () => {
      const duration = audio.duration
      const msg = chatHistory.value[pb.messageIndex]
      if (!msg || !msg.words) return
      const words = msg.words
      const indices: number[] = []
      let totalChars = 0
      for (let i = job.wordStart; i < job.wordEnd && i < words.length; i++) {
        const w = words[i]
        if (!w) continue
        const t = w.text.trim()
        if (t.length > 0) { indices.push(i); totalChars += t.length }
      }
      if (indices.length === 0 || !duration || !isFinite(duration) || totalChars === 0) return
      const timings: Array<{ i: number; t: number }> = []
      let acc = 0
      for (const idx of indices) {
        timings.push({ i: idx, t: acc })
        acc += (words[idx]!.text.trim().length / totalChars) * duration
      }
      let cursor = 0
      let lastScroll = 0
      intervalId = setInterval(() => {
        if (pb.cancelled || audio.paused || audio.ended) { clearTimer(); return }
        const ct = audio.currentTime || 0
        let revealed = false
        while (cursor < timings.length) {
          const tm = timings[cursor]
          if (!tm || ct < tm.t) break
          const w = words[tm.i]
          if (w) { w.visible = true; revealed = true }
          cursor++
        }
        if (revealed) {
          const now = Date.now()
          if (now - lastScroll >= 200) { scrollToBottom(); lastScroll = now }
        }
      }, 50)
    }

    const onReady = () => {
      if (pb.cancelled) { cleanup(); resolve(); return }
      if (!pb.firstStarted) {
        pb.firstStarted = true
        const msg = chatHistory.value[pb.messageIndex]
        if (msg) msg.audioReady = true // reveal the bubble on the first clip
        isPlayingResponseAudio.value = true
      }
      startPrinter()
      audio.play().catch(() => { finish() })
    }

    audio.onended = () => finish()
    audio.onerror = () => finish()

    if (audio.readyState >= 2) {
      onReady()
    } else {
      audio.addEventListener('canplay', onReady, { once: true })
      audio.addEventListener('loadedmetadata', () => { if (audio.readyState >= 2) onReady() }, { once: true })
    }
  })
}

// Sequential player: consume queued sentence clips strictly in order.
const runSentencePlayer = async (pb: PlaybackSession): Promise<void> => {
  while (true) {
    if (pb.cancelled) return
    if (pb.nextIndex >= pb.queue.length) {
      if (pb.finished) return
      await new Promise<void>(resolve => { pb.wake = resolve })
      pb.wake = null
      continue
    }
    const job = pb.queue[pb.nextIndex]
    pb.nextIndex++
    if (!job) continue
    let blob: Blob | null = null
    try {
      blob = await job.promise
    } catch {
      if (pb.cancelled) return
      // This sentence's TTS failed: reveal its text without audio and continue.
      const msg = chatHistory.value[pb.messageIndex]
      if (msg && msg.audioReady === false) msg.audioReady = true
      revealWordRange(pb, job.wordStart, job.wordEnd)
      await scrollToBottom()
      continue
    }
    if (pb.cancelled || !blob) return
    await playSentenceClip(pb, job, blob)
  }
}

// Stop and fully tear down the active streaming playback (if any).
const cancelPlayback = () => {
  const pb = currentPlayback
  if (!pb) return
  pb.cancelled = true
  for (const job of pb.queue) {
    try { job.abort.abort() } catch { /* ignore */ }
  }
  if (pb.activeAudio) {
    try { pb.activeAudio.pause() } catch { /* ignore */ }
    pb.activeAudio.currentTime = 0
    if (currentAudio === pb.activeAudio) currentAudio = null
    pb.activeAudio = null
  }
  if (pb.activeUrl && pb.activeUrl.startsWith('blob:')) {
    URL.revokeObjectURL(pb.activeUrl)
    pb.activeUrl = null
  }
  pb.wake?.()
  if (currentPlayback === pb) currentPlayback = null
}

const pushErrorReply = async () => {
  chatHistory.value.push({
    role: 'assistant',
    content: 'Sorry, I encountered an error. Please try again.',
    time: getCurrentTime()
  })
  await scrollToBottom()
}

const processAudio = async (audioBlob: Blob, mimeType: string) => {
  if (teacherMode.value) {
    await transcribeIntoDraft(audioBlob, mimeType)
    return
  }
  isLoading.value = true
  try {
    // Question-asking version: what the child said is sent straight away
    const userMessage = await transcribeWithBackend(audioBlob)
    await sendUserMessage(userMessage, { blob: audioBlob, mimeType }, null)
  } catch (error) {
    console.error('Error processing audio:', error)
    await pushErrorReply()
  } finally {
    isLoading.value = false
  }
}

/** Teacher version: add a recording's transcript to the end of the editable box */
const transcribeIntoDraft = async (audioBlob: Blob, mimeType: string) => {
  isTranscribing.value = true
  transcribeFailed.value = false
  try {
    const text = (await transcribeWithBackend(audioBlob)).trim()
    if (!text) {
      transcribeFailed.value = true
      return
    }
    const before = draft.value.trimEnd()
    draft.value = before ? `${before} ${text}` : text
    draftTranscripts.push(text)
    draftAudio = { blob: audioBlob, mimeType }
    // Ready to correct: cursor at the end of the text
    await nextTick()
    const box = draftBox.value
    if (box) {
      box.focus()
      box.setSelectionRange(box.value.length, box.value.length)
      box.scrollTop = box.scrollHeight
    }
  } catch (error) {
    console.error('Error transcribing audio:', error)
    transcribeFailed.value = true
  } finally {
    isTranscribing.value = false
  }
}

/** Teacher version: send the box's (possibly edited) text */
const sendDraft = async () => {
  if (!canSend.value) return
  const text = draft.value.trim()
  const audio = draftAudio
  const transcript = draftTranscripts.length > 0 ? draftTranscripts.join(' ') : null
  draft.value = ''
  draftAudio = null
  draftTranscripts = []
  transcribeFailed.value = false
  isLoading.value = true
  try {
    await sendUserMessage(text, audio, transcript)
  } catch (error) {
    console.error('Error sending message:', error)
    await pushErrorReply()
  } finally {
    isLoading.value = false
  }
}

const handleDraftKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    sendDraft()
  }
}

/**
 * Add the user's message to the chat and stream Nova's reply. The question-asking
 * version speaks the reply sentence by sentence as it streams; the teacher
 * version shows the text as it streams, with no speech. `transcript` is the raw
 * speech-to-text result when the teacher edited it (teacher version only).
 */
const sendUserMessage = async (
  userMessage: string,
  audio: { blob: Blob; mimeType: string } | null,
  transcript: string | null
) => {
  const speak = !teacherMode.value

  chatHistory.value.push({
    role: 'user',
    content: userMessage,
    time: getCurrentTime()
  })

  await scrollToBottom()

  // Get AI response using streaming chat completion
  const audioBase64 = audio ? await blobToBase64(audio.blob) : undefined
  const mimeType = audio?.mimeType

  // Placeholder for the reply, hidden until its first clip plays (or, without
  // speech, until its first words arrive)
  const assistantMessageIndex = chatHistory.value.length
  chatHistory.value.push({
    role: 'assistant',
    content: '',
    time: getCurrentTime(),
    words: speak ? [] : undefined,
    audioReady: false
  })

  // Start a fresh sentence-by-sentence playback session for this turn.
  cancelPlayback()
  const playback: PlaybackSession | null = speak
    ? {
        messageIndex: assistantMessageIndex,
        queue: [],
        nextIndex: 0,
        finished: false,
        cancelled: false,
        firstStarted: false,
        wake: null,
        activeAudio: null,
        activeUrl: null
      }
    : null
  currentPlayback = playback
  const playerPromise = playback ? runSentencePlayer(playback) : Promise.resolve()

  let fullText = ''
  let pendingText = '' // streamed text not yet emitted as a sentence
  let emittedSentenceCount = 0
  let nextState: typeof convState.value = convState.value
  
  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: chatHistory.value.slice(0, -1).map(msg => ({
          role: msg.role,
          content: msg.content
        })),
        state: convState.value,
        image_path: props.selectedImagePath,
        conversation_id: conversationId.value,
        session_id: sessionId.value,
        user_audio: audioBase64,
        user_audio_mime_type: mimeType,
        user_transcript: transcript ?? undefined,
        phenomenon: phenomenon.value?.id,
        version: version.value
      })
    })

    if (!response.ok) {
      throw new Error('Chat completion failed')
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    
    if (!reader) {
      throw new Error('No response body')
    }
    
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      const lines = buffer.split('\n')
      
      // Keep the last incomplete line in buffer
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.trim() === '') continue
        
        if (line.startsWith('data: ')) {
          try {
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue
            
            const data = JSON.parse(jsonStr)
            
            if (data.type === 'token') {
              const delta = data.content || ''
              fullText += delta
              pendingText += delta
              // Update stored content (bubble stays hidden until first audio)
              const assistantMsg = chatHistory.value[assistantMessageIndex]
              if (assistantMsg) {
                assistantMsg.content = fullText
              }
              if (!playback) {
                // No speech: the text appears as it streams
                if (assistantMsg && fullText.trim()) assistantMsg.audioReady = true
                scrollToBottom()
                continue
              }
              // Detect complete sentences and start their TTS immediately.
              let piece = extractLeadingSentence(pendingText, emittedSentenceCount === 0)
              while (piece) {
                enqueueSentence(playback, piece.sentence)
                emittedSentenceCount++
                pendingText = piece.rest
                piece = extractLeadingSentence(pendingText, emittedSentenceCount === 0)
              }
            } else if (data.type === 'done') {
              fullText = data.response || fullText
              nextState = data.next_state as typeof convState.value
              convState.value = nextState
              // Flush any trailing text as the final sentence (use the streamed
              // remainder so word offsets stay aligned with the clips we fired).
              if (playback) {
                if (pendingText.trim().length > 0) {
                  enqueueSentence(playback, pendingText)
                  pendingText = ''
                  emittedSentenceCount++
                }
                playback.finished = true
                playback.wake?.()
              }
              const assistantMsg = chatHistory.value[assistantMessageIndex]
              if (assistantMsg) {
                assistantMsg.content = fullText
                if (!playback && fullText.trim()) assistantMsg.audioReady = true
              }
              // Final scroll when done
              await scrollToBottom()
            } else if (data.type === 'error') {
              const errorMsg = data.error || 'Streaming error'
              console.error('Stream error received:', errorMsg)
              // If we have partial text, continue with it; otherwise throw error
              if (!fullText || fullText.trim().length === 0) {
                throw new Error(errorMsg)
              } else {
                // We have partial text, log the error but continue
                console.warn('Stream error occurred but continuing with partial response')
              }
            }
          } catch (e) {
            // Rethrow stream errors (e.g. an 'error' event with no text) so the
            // outer catch falls back to /api/chat; only swallow JSON parse errors.
            if (!(e instanceof SyntaxError)) throw e
            if (line.slice(6).trim().length > 0) {
              console.error('Error parsing SSE data:', e, 'Line:', line.substring(0, 100))
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('Error in streaming:', error)
    // Stop any sentence clips already queued/playing before the whole-text fallback.
    cancelPlayback()
    // Fallback to regular non-streaming endpoint
    try {
      const chatResponse = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messages: chatHistory.value.slice(0, -1).map(msg => ({
            role: msg.role,
            content: msg.content
          })),
          state: convState.value,
          image_path: props.selectedImagePath,
          conversation_id: conversationId.value,
          session_id: sessionId.value,
          user_audio: audioBase64,
          user_audio_mime_type: mimeType,
          user_transcript: transcript ?? undefined,
          phenomenon: phenomenon.value?.id,
          version: version.value
        })
      })
      
      if (!chatResponse.ok) {
        throw new Error('Chat completion failed')
      }
      
      const chatData = await chatResponse.json()
      fullText = chatData.response
      nextState = chatData.next_state as typeof convState.value
      convState.value = nextState
      
      if (!speak) {
        const assistantMsg = chatHistory.value[assistantMessageIndex]
        if (assistantMsg) {
          assistantMsg.content = fullText
          assistantMsg.audioReady = true
        }
        await scrollToBottom()
        return
      }

      // Update the assistant message
      const words = fullText.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
        text: w,
        visible: false
      }))
      const assistantMsg = chatHistory.value[assistantMessageIndex]
      if (assistantMsg) {
        assistantMsg.words = words
        assistantMsg.content = fullText
        assistantMsg.audioReady = false
      }
      
      await scrollToBottom()
      await generateAndPlayAudioWithPrinterEffect(fullText, assistantMessageIndex)
      return
    } catch (fallbackError) {
      console.error('Fallback also failed:', fallbackError)
      throw error // Throw original error
    }
  }
  
  if (!playback) {
    const assistantMsg = chatHistory.value[assistantMessageIndex]
    if (assistantMsg) {
      if (!fullText.trim()) {
        console.error('No text received from stream')
        assistantMsg.content = 'Sorry, I encountered an error generating a response. Please try again.'
      }
      assistantMsg.audioReady = true
    }
    await scrollToBottom()
    return
  }

  // Stream ended. Flush any trailing text and let the player finish all clips.
  // (Normally the 'done' event already flushed and set finished; this also covers
  // a stream that ended without a 'done' event, e.g. a mid-stream error that still
  // produced partial text.)
  if (pendingText.trim().length > 0) {
    enqueueSentence(playback, pendingText)
    pendingText = ''
  }
  playback.finished = true
  playback.wake?.()

  if (playback.queue.length === 0) {
    // Nothing usable was generated.
    console.error('No text received from stream')
    cancelPlayback()
    const assistantMsg = chatHistory.value[assistantMessageIndex]
    if (assistantMsg) {
      if (!fullText || fullText.trim().length === 0) {
        assistantMsg.content = 'Sorry, I encountered an error generating a response. Please try again.'
      }
      assistantMsg.audioReady = true // show message even without audio
    }
    await scrollToBottom()
    return
  }

  // Wait until every sentence clip has finished playing (keeps the mic disabled
  // while Nova is still talking, matching the previous behavior).
  await playerPromise
  isPlayingResponseAudio.value = false
  if (currentPlayback === playback) currentPlayback = null
}

const generateAndPlayAudio = async (text: string) => {
  try {
    // Validate text before sending
    if (!text || typeof text !== 'string' || text.trim().length === 0) {
      console.error('Cannot generate speech: text is empty or invalid')
      return
    }
    
    const response = await fetch('/api/speech', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text: text.trim() })
    })
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error')
      console.error('Speech generation failed:', response.status, errorText)
      throw new Error(`Speech generation failed: ${response.status}`)
    }
    
    const audioBlob = await response.blob()
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = atNovaRate(new Audio(audioUrl))
    
    // Store reference to current audio
    currentAudio = audio
    
    audio.onended = () => {
      isPlayingResponseAudio.value = false
      URL.revokeObjectURL(audioUrl)
      if (currentAudio === audio) {
        currentAudio = null
      }
    }
    
    isPlayingResponseAudio.value = true
    await audio.play()
  } catch (error) {
    isPlayingResponseAudio.value = false
    console.error('Error playing audio:', error)
  }
}

const generateAndPlayAudioWithPrinterEffect = async (
  text: string,
  messageIndex: number
) => {
  try {
    // Validate text before sending
    if (!text || typeof text !== 'string' || text.trim().length === 0) {
      console.error('Cannot generate speech: text is empty or invalid')
      // Show message without audio
      const message = chatHistory.value[messageIndex]
      if (message) {
        message.audioReady = true
      }
      return
    }
    
    const response = await fetch('/api/speech', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ text: text.trim() })
    })
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error')
      console.error('Speech generation failed:', response.status, errorText)
      throw new Error(`Speech generation failed: ${response.status}`)
    }
    
    const audioBlob = await response.blob()
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = atNovaRate(new Audio(audioUrl))
    
    // Store reference to current audio
    currentAudio = audio
    
    // Get words array for this message
    const message = chatHistory.value[messageIndex]
    if (!message) {
      // Fallback to regular playback if message doesn't exist
      await generateAndPlayAudio(text)
      return
    }
    if (!message.words) {
      // Fallback to regular playback if words array doesn't exist
      await generateAndPlayAudio(text)
      return
    }
    
    // Load audio to get duration
    const setupPrinterEffect = () => {
      const onReady = () => {
        // Show message bubble when audio is ready
        if (message) {
          message.audioReady = true
        }
        startPrinterEffect()
      }
      
      if (audio.readyState >= 2) {
        // Can play - metadata and some data loaded
        onReady()
      } else {
        // Wait for canplay event to ensure audio is ready
        audio.addEventListener('canplay', onReady, { once: true })
        // Also listen for loadedmetadata as fallback
        audio.addEventListener('loadedmetadata', () => {
          if (audio.readyState >= 2) {
            onReady()
          }
        }, { once: true })
      }
    }
    
    const startPrinterEffect = () => {
      const duration = audio.duration
      if (!message || !message.words) return
      const words = message.words
      
      // Filter out whitespace-only tokens and calculate timings
      const wordIndices: number[] = []
      let totalChars = 0
      
      for (let i = 0; i < words.length; i++) {
        const word = words[i]
        if (!word) continue
        const trimmed = word.text.trim()
        if (trimmed.length > 0) {
          wordIndices.push(i)
          totalChars += trimmed.length
        }
      }
      
      if (wordIndices.length === 0) {
        // No words to reveal, just play audio - still resolve when audio ends
        audio.onended = () => {
          isPlayingResponseAudio.value = false
          URL.revokeObjectURL(audioUrl)
          if (currentAudio === audio) currentAudio = null
          resolveAudioEnded()
        }
        return
      }
      
      // Calculate timing for each word based on character count
      const wordTimings: Array<{wordIndex: number, time: number}> = []
      let currentTime = 0
      
      for (const wordIdx of wordIndices) {
        if (!words[wordIdx]) continue
        const wordLength = words[wordIdx].text.trim().length
        const timeForWord = (wordLength / totalChars) * duration
        wordTimings.push({ wordIndex: wordIdx, time: currentTime })
        currentTime += timeForWord
      }
      
      // Reveal words as audio plays
      let currentWordIndex = 0
      let lastScrollTime = 0
      const scrollThrottle = 200 // Throttle scrolling to every 200ms during printer effect
      const updateInterval = setInterval(() => {
        if (!audio || audio.paused || audio.ended) {
          clearInterval(updateInterval)
          return
        }
        
        const currentAudioTime = audio.currentTime || 0
        let wordsRevealed = false
        
        // Reveal words that should be visible at current time
        while (currentWordIndex < wordTimings.length) {
          const timing = wordTimings[currentWordIndex]
          if (!timing || currentAudioTime < timing.time) break
          const wordIdx = timing.wordIndex
          if (wordIdx !== undefined && words && words[wordIdx]) {
            words[wordIdx].visible = true
            wordsRevealed = true
          }
          currentWordIndex++
        }
        
        // Auto-scroll when new words are revealed (throttled)
        if (wordsRevealed) {
          const now = Date.now()
          if (now - lastScrollTime >= scrollThrottle) {
            scrollToBottom()
            lastScrollTime = now
          }
        }
      }, 50) // Update every 50ms for smooth effect
      
      audio.onended = () => {
        isPlayingResponseAudio.value = false
        clearInterval(updateInterval)
        // Make sure all words are visible at the end
        if (words) {
          words.forEach(word => word.visible = true)
        }
        // Final scroll when audio ends
        scrollToBottom()
        URL.revokeObjectURL(audioUrl)
        if (currentAudio === audio) {
          currentAudio = null
        }
        resolveAudioEnded()
      }
    }
    
    let resolveAudioEnded!: () => void
    const audioEndedPromise = new Promise<void>(r => { resolveAudioEnded = r })
    
    setupPrinterEffect()
    
    isPlayingResponseAudio.value = true
    await audio.play()
    await audioEndedPromise
  } catch (error) {
    isPlayingResponseAudio.value = false
    console.error('Error playing audio with printer effect:', error)
    // Fallback to regular playback
    await generateAndPlayAudio(text)
  }
}


const loadExistingConversation = async () => {
  try {
    // Get the most recent conversation for this session
    // Only this version's conversations: QA and teacher chats never mix
    const params = new URLSearchParams({ session_id: sessionId.value, version: version.value })
    const response = await fetch(`/api/conversations?${params}`)
    if (!response.ok) {
      console.error('Failed to fetch conversations:', response.status, response.statusText)
      throw new Error('Failed to fetch conversations')
    }
    
    const data = await response.json()
    const conversations = data.conversations || []
    
    if (conversations.length === 0) {
      return false
    }
    
    // Normalize image path for comparison - extract just the filename
    const currentImage = props.selectedImagePath || '/imgs/balloon.jpg'
    const normalizeImagePath = (path: string | null | undefined) => {
      if (!path) return ''
      // Normalize path: extract just the filename, case-insensitive
      let normalized = path.trim()
      // Remove leading slashes
      normalized = normalized.replace(/^\/+/, '')
      // Remove 'imgs/' prefix if present
      normalized = normalized.replace(/^imgs\//, '')
      // Remove leading slash again in case it was added back
      normalized = normalized.replace(/^\/+/, '')
      // Extract just the filename (last part after /)
      const filename = normalized.split('/').pop() || normalized
      // Normalize to lowercase for comparison
      return filename.toLowerCase()
    }
    const normalizedCurrentImage = normalizeImagePath(currentImage)
    
    // Only look for conversations with the exact same image - strict isolation
    // First, try to find the most recent unfinished conversation with the same image
    let matchingConversation = conversations.find((conv: any) => {
      const normalizedConvImage = normalizeImagePath(conv.image_path)
      return normalizedConvImage === normalizedCurrentImage && !conv.finished_at
    })
    
    // If no unfinished conversation found, get the most recent conversation with the same image
    if (!matchingConversation) {
      const sameImageConvs = conversations.filter((conv: any) => {
        const normalizedConvImage = normalizeImagePath(conv.image_path)
        return normalizedConvImage === normalizedCurrentImage
      })
      if (sameImageConvs.length > 0) {
        // Get the most recent one (they're already sorted by updated_at desc)
        matchingConversation = sameImageConvs[0]
      }
    }
    
    // Strict isolation: If no match found for this image, don't load any conversation
    // This ensures conversations are completely isolated by image
    if (!matchingConversation) {
      return false
    }
    
    if (matchingConversation) {
      // Load the conversation
      conversationId.value = matchingConversation.id
      
      // Get messages for this conversation
      const messagesResponse = await fetch(`/api/conversations/${conversationId.value}/messages`)
      if (messagesResponse.ok) {
        const messagesData = await messagesResponse.json()
        const messages = messagesData.messages || []
        
        if (messages.length === 0) {
          return false
        }
        
        // Restore chat history from messages
        // Filter out system messages and only include user and assistant messages
        const greetingText = openingLine.value
        
        chatHistory.value = messages
          .filter((msg: any) => msg.role === 'user' || msg.role === 'assistant')
          .map((msg: any) => {
            return {
              role: msg.role,
              content: msg.content,
              time: new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              words: msg.role === 'assistant' ? msg.content.split(/(\s+)/).filter((w: string) => w.length > 0).map((w: string) => ({
                text: w,
                visible: true // Already visible since it's loaded
              })) : undefined,
              audioReady: msg.role === 'assistant' ? true : undefined
            }
          })
        
        // Check if the greeting message is already in the history
        const firstMessage = chatHistory.value[0]
        const hasGreetingMessage = chatHistory.value.length > 0 && 
          firstMessage && 
          firstMessage.role === 'assistant' && 
          firstMessage.content === greetingText
        
        // If no greeting message found, prepend it as the default opening message
        if (!hasGreetingMessage) {
          const greetingWords = greetingText.split(/(\s+)/).filter((w: string) => w.length > 0).map((w: string) => ({
            text: w,
            visible: true // Already visible since it's loaded
          }))
          const firstExistingMessage = chatHistory.value[0]
          chatHistory.value.unshift({
            role: 'assistant',
            content: greetingText,
            time: firstExistingMessage?.time || getCurrentTime(),
            words: greetingWords,
            audioReady: true
          })
        }
        
        // Get the current state from the conversation
        const convResponse = await fetch(`/api/conversations/${conversationId.value}`)
        if (convResponse.ok) {
          const convData = await convResponse.json()
          convState.value = convData.current_state || 'greet'
        }

        await scrollToBottom()
        return true // Conversation loaded
      } else {
        console.error('Failed to fetch messages:', messagesResponse.status)
      }
    }
    
    return false // No conversation to load
  } catch (error) {
    console.error('Error loading existing conversation:', error)
    return false
  }
}

const generateInitialGreeting = async () => {
  const greetingText = openingLine.value
  
  // Prevent duplicate greeting calls - check if greeting already exists in chat history
  const hasGreeting = chatHistory.value.some(msg => 
    msg.role === 'assistant' && msg.content === greetingText
  )
  if (isGeneratingGreeting.value || hasGreeting) {
    return
  }
  
  isGeneratingGreeting.value = true
  
  try {
    
    // Ensure conversation exists in database before trying to add messages
    let conversationCreated = false
    try {
      const createConvResponse = await fetch('/api/conversations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          id: conversationId.value,
          session_id: sessionId.value,
          image_path: props.selectedImagePath || '/imgs/balloon.jpg',
          phenomenon: phenomenon.value?.id,
          version: version.value
        })
      })
      
      if (!createConvResponse.ok) {
        const errorText = await createConvResponse.text().catch(() => 'Unknown error')
        console.error('Failed to create conversation:', createConvResponse.status, errorText)
        throw new Error(`Failed to create conversation: ${createConvResponse.status}`)
      }
      
      // Parse response to verify conversation was created and get the actual ID
      const convData = await createConvResponse.json()
      if (convData.id) {
        // Use the ID from the response (could be new or existing conversation)
        conversationId.value = convData.id
        conversationCreated = true
      } else {
        throw new Error('Conversation creation response missing ID')
      }
    } catch (error) {
      console.error('Error creating conversation:', error)
      // Don't continue if conversation creation failed
      return
    }
    
    // Don't proceed if conversation wasn't successfully created/verified
    if (!conversationCreated) {
      console.error('Conversation was not created successfully')
      return
    }
    
    // Save greeting message to database
    try {
      const response = await fetch(`/api/conversations/${conversationId.value}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          role: 'assistant',
          content: greetingText,
          state: 'greet'
        })
      })
      
      if (!response.ok) {
        console.error('Failed to save greeting message to database')
      }
    } catch (error) {
      console.error('Error saving greeting message:', error)
    }
    
    if (teacherMode.value) {
      // No speech in the teacher version: the line is just shown
      chatHistory.value.push({
        role: 'assistant',
        content: greetingText,
        time: getCurrentTime()
      })
      await scrollToBottom()
      return
    }

    // Split text into words for printer effect
    const words = greetingText.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
      text: w,
      visible: false
    }))
    
    // Add greeting message to chat history (hidden until audio is ready)
    const greetingIndex = chatHistory.value.length
    chatHistory.value.push({
      role: 'assistant',
      content: greetingText,
      time: getCurrentTime(),
      words: words,
      audioReady: false
    })
    
    await scrollToBottom()
    
    // Generate and play audio for the greeting with printer effect
    await generateAndPlayAudioWithPrinterEffect(greetingText, greetingIndex)
  } finally {
    isGeneratingGreeting.value = false
  }
}

const startNewChat = async () => {
  if (isLoading.value) return

  roomChoiceShowPending.value = false

  // Stop any playing audio (streaming sentence clips + standalone playback)
  cancelPlayback()
  isPlayingResponseAudio.value = false
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
    if (currentAudio.src && currentAudio.src.startsWith('blob:')) {
      URL.revokeObjectURL(currentAudio.src)
    }
    currentAudio = null
  }

  // Create a new conversation ID but keep the same session ID
  conversationId.value = crypto.randomUUID()
  
  // Clear the chat history
  chatHistory.value = []
  convState.value = 'greet'
  
  // Generate initial greeting for the new conversation
  await generateInitialGreeting()
}

// Header restart button: a fresh conversation in this room, Nova greets again.
// Not before the chat has loaded (the first greeting would race it).
const canRestartChat = computed(
  () =>
    chatHistory.value.length > 0 &&
    !novaBusy.value &&
    !isRecording.value &&
    !isTranscribing.value
)

const restartChat = async () => {
  if (!canRestartChat.value) return
  draft.value = ''
  draftTranscripts = []
  draftAudio = null
  transcribeFailed.value = false
  await startNewChat()
}

const handleKeyDown = (e: KeyboardEvent) => {
  // Typing in the teacher's box: Space is just a space
  const target = e.target as HTMLElement | null
  if (target?.closest?.('textarea, input, select, [contenteditable="true"]')) return
  const locked = teacherMode.value ? micLocked.value : isLoading.value
  if (e.code === 'Space' && !e.repeat && !locked) {
    e.preventDefault()
    if (isRecording.value) {
      stopRecording()
    } else {
      startRecording()
    }
  }
}

// Watch for chat history changes to update scroll state
watch(chatHistory, async () => {
  await nextTick()
  updateScrollState()
}, { deep: true })

// When 10-min / 30-min timer fired during TTS, show popup only after playback ends
watch(isPlayingResponseAudio, (playing) => {
  if (playing) return
  if (missionCompleteShowPending.value) {
    missionCompleteShowPending.value = false
    roomChoiceShowPending.value = false
    showMissionCompletePopup.value = true
    sessionStorage.setItem(MISSION_COMPLETE_SHOWN_KEY, '1')
  } else if (roomChoiceShowPending.value) {
    roomChoiceShowPending.value = false
    showRoomChoicePopup.value = true
  }
})

// Watch for image path changes and reload conversation if needed
watch(() => props.selectedImagePath, async (newPath, oldPath) => {
  // If image path changes, always reload conversation for the new image
  if (newPath !== oldPath) {
    startRoomChoiceTimer()
    // Stop any playing audio first (streaming sentence clips + standalone playback)
    cancelPlayback()
    isPlayingResponseAudio.value = false
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.currentTime = 0
      if (currentAudio.src && currentAudio.src.startsWith('blob:')) {
        URL.revokeObjectURL(currentAudio.src)
      }
      currentAudio = null
    }

    // Clear current state
    chatHistory.value = []
    convState.value = 'greet'
    
    // Try to load conversation for new image
    const conversationLoaded = await loadExistingConversation()
    if (!conversationLoaded) {
      // If no conversation found for this image, start a new one
      conversationId.value = crypto.randomUUID()
      await generateInitialGreeting()
    }
  }
}, { immediate: false })

onMounted(async () => {
  document.addEventListener('keydown', handleKeyDown)
  startRoomChoiceTimer()
  ensureFirstConversationClockAnchor()
  scheduleMissionCompleteTimer()

  // Wait for props to be set (may take a moment if parent sets them in onMounted)
  let attempts = 0
  while (!props.selectedImagePath && attempts < 10) {
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))
    attempts++
  }
  
  // Try to load existing conversation for the current image first
  // This ensures we only load conversations that match the selected image
  const conversationLoaded = await loadExistingConversation()
  
  // If no conversation was loaded for this image, generate initial greeting
  if (!conversationLoaded) {
    conversationId.value = crypto.randomUUID()
    await generateInitialGreeting()
  }
  
  // Initialize scroll state
  updateScrollState()

  if (import.meta.env.DEV) {
    const w = window as Window & {
      __curioDebug?: {
        showRoomChoice: () => void
        showMissionComplete: () => void
        resetMissionShownFlag: () => void
      }
    }
    w.__curioDebug = {
      showRoomChoice: () => {
        showMissionCompletePopup.value = false
        showRoomChoicePopup.value = true
      },
      showMissionComplete: () => {
        showRoomChoicePopup.value = false
        showMissionCompletePopup.value = true
      },
      resetMissionShownFlag: () => {
        sessionStorage.removeItem(MISSION_COMPLETE_SHOWN_KEY)
      }
    }
  }
})

onUnmounted(() => {
  if (import.meta.env.DEV) {
    const w = window as Window & { __curioDebug?: unknown }
    delete w.__curioDebug
  }
  document.removeEventListener('keydown', handleKeyDown)

  if (roomChoiceTimeout) {
    clearTimeout(roomChoiceTimeout)
    roomChoiceTimeout = null
  }
  roomChoiceShowPending.value = false

  if (missionCompleteTimeout) {
    clearTimeout(missionCompleteTimeout)
    missionCompleteTimeout = null
  }
  missionCompleteShowPending.value = false
  
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }

  // Stop any playing audio (streaming sentence clips + standalone playback)
  cancelPlayback()
  isPlayingResponseAudio.value = false
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
    // Revoke object URL to free memory
    if (currentAudio.src && currentAudio.src.startsWith('blob:')) {
      URL.revokeObjectURL(currentAudio.src)
    }
    currentAudio = null
  }
})

// Expose methods and state to parent component
defineExpose({
  startNewChat,
  isLoading
})
</script>

<style scoped>
/* "ASK NOVA ANYTHING!" panel from the Lab-Design chat frames (03D, 04D, 05E, 07B-09B).
   Sizes are Figma pixels: the panel is 528×699 inside a FigmaStage. */
.chat-container {
  --panel-border: var(--curio-navy);
  --panel-header: #05365c;
  --panel-body: var(--curio-cream);
  --bubble-rim: #7695ce;
  --bubble-nova: #05365c;
  --bubble-child: #fec566;
  --panel-footer: #c0c9d6;
  --voice-btn-size: 112px;
  --voice-btn-width: 120px;

  width: 100%;
  height: 100%;
  box-sizing: border-box;
  background: var(--panel-body);
  border: 8px solid var(--panel-border);
  border-radius: 30px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  z-index: 200;
  box-shadow: 0 14px 30px rgba(25, 52, 79, 0.25);
}

.chat-panel-header {
  position: relative;
  flex-shrink: 0;
  height: 92px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--panel-header);
}

.chat-panel-title {
  margin: 0;
  font-family: var(--curio-font-mono);
  font-weight: 700;
  font-size: 30px;
  letter-spacing: 0.02em;
  color: #ffffff;
}

/* Restart this chat: a plain round icon button at the header's right end */
.restart-chat-button {
  position: absolute;
  right: 20px;
  top: 50%;
  width: 50px;
  height: 50px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 3px solid rgba(255, 255, 255, 0.85);
  border-radius: 50%;
  background: transparent;
  color: #ffffff;
  font-size: 22px;
  cursor: pointer;
  transform: translateY(-50%);
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}

.restart-chat-button:hover:not(:disabled) {
  background: var(--curio-yellow);
  border-color: var(--curio-yellow);
  color: var(--curio-navy);
}

.restart-chat-button:active:not(:disabled) {
  transform: translateY(-50%) scale(0.94);
}

.restart-chat-button:focus-visible {
  outline: 4px solid var(--curio-yellow);
  outline-offset: 3px;
}

.restart-chat-button:disabled {
  opacity: 0.35;
  cursor: default;
}

/* Messages */
.chat-messages {
  flex: 1;
  min-height: 0;
  padding: 18px 22px calc(12px + var(--voice-btn-size) / 2);
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--panel-body);
  position: relative;
  z-index: 1;
}

.message {
  margin-bottom: 18px;
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-inner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 92%;
}

.message.user .message-inner {
  margin-left: auto;
  justify-content: flex-end;
}

.message-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  margin-top: 4px;
}

.message-bubble {
  padding: 16px 22px;
  border: 4px solid var(--bubble-rim);
  border-radius: 20px;
  font-family: var(--curio-font-round);
  font-size: 18px;
  font-weight: 500;
  transition: opacity 0.3s ease-in;
}

/* The corner nearest the speaker is square, like a speech-bubble tail */
.message.assistant .message-bubble {
  background: var(--bubble-nova);
  color: #ffffff;
  border-bottom-left-radius: 4px;
}

.message.user .message-bubble {
  background: var(--bubble-child);
  color: var(--curio-navy);
  border-bottom-right-radius: 4px;
}

.message-text {
  line-height: 1.6;
  text-align: left;
}

.message-text :deep(.bold-highlight),
.message-text .bold-highlight {
  font-weight: 700;
  display: inline;
}

.message.assistant .message-text :deep(.bold-highlight),
.message.assistant .message-text .bold-highlight {
  color: var(--curio-yellow);
}

.message.user .message-text :deep(.bold-highlight),
.message.user .message-text .bold-highlight {
  color: var(--curio-navy-deep);
}

.word-visible {
  opacity: 1;
  transition: opacity 0.1s ease-in;
}

.word-hidden {
  opacity: 0;
}

/* Footer: the mic sits half above the bar */
.chat-input-area {
  flex-shrink: 0;
  height: 100px;
  box-sizing: border-box;
  padding: 0 12px 14px;
  position: relative;
  z-index: 4;
  background: var(--panel-footer);
  border-top: 4px solid var(--bubble-rim);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.voice-input-container {
  position: absolute;
  left: 50%;
  top: calc(-0.5 * var(--voice-btn-size));
  transform: translateX(-50%);
}

.voice-input-button {
  width: var(--voice-btn-width);
  height: var(--voice-btn-size);
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, filter 0.2s ease;
}

.voice-input-button:hover:not(:disabled) {
  transform: scale(1.05);
}

.voice-input-button:active:not(:disabled) {
  transform: scale(0.96);
}

.voice-input-button:focus-visible {
  outline: 4px solid var(--curio-yellow);
  outline-offset: 2px;
}

.voice-input-button.recording {
  animation: pulse 1.2s ease-in-out infinite;
}

/* While listening the mic stays in place and throbs (grows and shrinks), in step
   with the glow */
.voice-input-button.recording .voice-icon {
  animation: throb 1.2s ease-in-out infinite;
}

@keyframes throb {
  0%, 100% { transform: scale(0.9); }
  50% { transform: scale(1.1); }
}

.voice-input-button.loading,
.voice-input-button:disabled {
  cursor: not-allowed;
}

/* Same navy disc as the mic artwork, drawn without the mic glyph */
.voice-loading-face {
  width: 110px;
  height: 110px;
  box-sizing: border-box;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% 38%, #2d5f96 0%, #1a4677 55%, #0f3157 100%);
  border: 6px solid #0b2a4a;
  box-shadow: inset 0 3px 0 rgba(255, 255, 255, 0.18), 0 4px 10px rgba(11, 42, 74, 0.35);
}

.voice-icon {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.loading-icon {
  font-size: 40px;
  color: #ffffff;
}

@keyframes pulse {
  0%, 100% { filter: drop-shadow(0 0 0 rgba(255, 211, 77, 0)); }
  50% { filter: drop-shadow(0 0 14px rgba(255, 211, 77, 0.9)); }
}

/* Teacher version footer: editable box on top; mic, status and Send below.
   The mic sits inside the bar here, so the messages need no extra room for it. */
.chat-container.teacher .chat-messages {
  padding-bottom: 18px;
}

.chat-input-area.teacher-input {
  height: auto;
  padding: 14px 16px;
  gap: 10px;
  justify-content: flex-start;
}

.draft-box {
  width: 100%;
  box-sizing: border-box;
  margin: 0;
  padding: 10px 14px;
  resize: none;
  border: 4px solid var(--bubble-rim);
  border-radius: 16px;
  background: #ffffff;
  font-family: var(--curio-font-round);
  font-size: 18px;
  font-weight: 500;
  line-height: 1.5;
  color: var(--curio-navy);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.draft-box::placeholder {
  color: #6b7a8c;
}

.draft-box:focus {
  outline: none;
  border-color: var(--curio-navy);
  box-shadow: 0 0 0 4px rgba(255, 211, 77, 0.8);
}

.teacher-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.teacher-input .voice-input-button {
  flex: 0 0 auto;
  width: 77px;
  height: 72px;
}

.teacher-input .voice-loading-face {
  width: 70px;
  height: 70px;
  border-width: 4px;
}

.teacher-input .loading-icon {
  font-size: 28px;
}

.draft-status {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-family: var(--curio-font-mono);
  font-weight: 500;
  font-size: 15px;
  line-height: 1.3;
  color: #111111;
  text-align: left;
}

.draft-status.warn {
  color: #a4311f;
}

.send-button {
  flex: 0 0 auto;
  min-width: 128px;
  height: 60px;
  padding: 0 24px;
  border: 5px solid var(--curio-navy);
  border-radius: 999px;
  background: var(--curio-yellow);
  color: var(--curio-navy);
  font-family: var(--curio-font-mono);
  font-weight: 700;
  font-size: 24px;
  cursor: pointer;
  box-shadow: 0 4px 0 var(--curio-navy);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}

.send-button:hover:not(:disabled) {
  filter: brightness(1.05);
  transform: translateY(-2px);
}

.send-button:active:not(:disabled) {
  transform: translateY(3px);
  box-shadow: 0 1px 0 var(--curio-navy);
}

.send-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.send-button:focus-visible {
  outline: 4px solid var(--curio-yellow);
  outline-offset: 3px;
}

.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(25, 52, 79, 0.25);
  border-radius: 4px;
}

/* Popups (Frame 70 / 71): built from shapes and text, not images. The card and
   button look is shared (assets/popup.css). */
.room-choice-overlay,
.mission-complete-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 30, 50, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.25s ease;
}

.room-choice-title {
  font-weight: 700;
  font-size: 40px;
  margin-bottom: 10px;
}

.room-choice-question {
  font-weight: 600;
  font-size: 26px;
  line-height: 1.4;
  margin-bottom: 32px;
}

.room-choice-actions {
  display: flex;
  justify-content: center;
  gap: 32px;
}

.mission-complete-container {
  padding-right: 300px;
  text-align: left;
}

.mission-complete-message {
  font-weight: 700;
  font-size: 32px;
  line-height: 1.4;
  margin-bottom: 28px;
}

.happy-nova {
  position: absolute;
  right: -30px;
  bottom: -20px;
  width: 300px;
  pointer-events: none;
}

.star {
  position: absolute;
  pointer-events: none;
  animation: twinkle 1.6s ease-in-out infinite;
}

.star-1 { width: 72px; right: 236px; top: 34px; }
.star-2 { width: 56px; right: 44px; top: 26px; animation-delay: 0.4s; }
.star-3 { width: 84px; right: 250px; bottom: 36px; animation-delay: 0.8s; }

@keyframes twinkle {
  50% { transform: scale(1.12) rotate(8deg); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
