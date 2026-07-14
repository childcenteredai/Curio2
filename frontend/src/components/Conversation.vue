<template>
  <div class="chat-container">
    <header class="chat-panel-header">
      <h1 class="chat-panel-title">Let's Learn Together!</h1>
      <!-- <p class="chat-panel-subtitle">Ask me anything about this picture</p> -->
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
            src="/imgs/owl.svg"
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

    <!-- Voice input: click to start, click again to send -->
    <div class="chat-input-area">
      <div class="voice-input-container">
        <button 
          @click="handleVoiceClick"
          :disabled="isLoading"
          :class="`voice-input-button ${isRecording ? 'recording' : ''} ${isLoading ? 'loading' : ''}`"
          :title="isLoading ? 'Processing...' : isRecording ? 'Click to send' : 'Click to speak'"
        >
          <i
            v-if="isLoading"
            class="fa-solid fa-spinner fa-spin voice-icon loading-icon"
            aria-hidden="true"
          />
          <i
            v-else
            class="fa-solid fa-microphone voice-icon mic-icon"
            :class="{ 'recording-icon': isRecording }"
            aria-hidden="true"
          />
        </button>
      </div>
      <!-- <p class="voice-hint">💡 PRESS to describe what you see or ask questions!</p> -->
    </div>

    <!-- 10-min room choice popup -->
    <div
      v-if="showRoomChoicePopup"
      class="room-choice-overlay"
      @click.self.stop
    >
      <div class="room-choice-container" role="dialog" aria-modal="true" aria-label="Room choice">
        <div class="room-choice-title">Quick check-in</div>
        <div class="room-choice-question">
          Do you want to explore another room or continue exploring this room?
        </div>
        <div class="room-choice-actions">
          <button class="room-choice-button secondary" @click="handleExploreAnotherRoom">
            Another room
          </button>
          <button class="room-choice-button primary" @click="handleContinueThisRoom">
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
      <div class="mission-complete-container" role="dialog" aria-modal="true" aria-label="Session reminder">
        <div class="mission-complete-message">
          Excellent work! We successfully completed our detective mission today. Let's get back to your researcher!
        </div>
        <button type="button" class="mission-complete-button" @click="handleMissionCompleteDismiss">
          OK
        </button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { CURIO_APP_VERSION, loadAppConfig } from '../constants/appConfig'
// Use relative paths - works with nginx reverse proxy (local) and Ingress (prod)

// Props
const props = defineProps<{
  selectedImagePath?: string
}>()
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
// Get or create session_id from localStorage
const getOrCreateSessionId = (): string => {
  const stored = localStorage.getItem('curio_session_id')
  if (stored) {
    return stored
  }
  const newSessionId = crypto.randomUUID()
  localStorage.setItem('curio_session_id', newSessionId)
  return newSessionId
}
const sessionId = ref<string>(getOrCreateSessionId())
const isGeneratingGreeting = ref(false)

const router = useRouter()

const isPlayingResponseAudio = ref(false)

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
  router.push('/')
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

// Emit first-time matched concepts for concept bubbles (displayed in Home)
const emit = defineEmits<{
  (e: 'firstTimeMatchedConcepts', concepts: string[]): void
}>()

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
// Process words array and mark which words should be bold, and track first/last in sequence
const renderWordsWithBoldState = (words: Array<{text: string, visible: boolean}>): Array<{text: string, visible: boolean, isBold: boolean, isFirstBold?: boolean, isLastBold?: boolean}> => {
  if (!words) return []
  
  let isBold = false
  const processedWords: Array<{text: string, visible: boolean, isBold: boolean, isFirstBold?: boolean, isLastBold?: boolean}> = []
  
  // First pass: mark bold words
  for (const word of words) {
    let wordText = word.text
    
    // Check if this word contains '**'
    if (wordText.includes('**')) {
      // Count how many '**' markers are in this word
      const markerCount = (wordText.match(/\*\*/g) || []).length
      
      // Remove '**' markers from the text
      wordText = wordText.replace(/\*\*/g, '')
      
      let wordIsBold: boolean
      
      if (markerCount % 2 === 1) {
        // This is an opening or closing marker (odd count)
        // Opening marker: isBold is false → toggle to true, word should be true
        // Closing marker: isBold is true → word should be true, toggle to false
        if (!isBold) {
          // Opening marker: toggle first, then use new state
          isBold = true
          wordIsBold = true
        } else {
          // Closing marker: use current state, then toggle
          wordIsBold = true
          isBold = false
        }
      } else {
        // Even count: **word** - content between markers is bold
        wordIsBold = true
        isBold = false  // closed
      }
      
      processedWords.push({
        text: wordText,
        visible: word.visible,
        isBold: wordIsBold
      })
    } else {
      // No marker - don't highlight whitespace
      const isWhitespace = /^\s+$/.test(wordText)
      processedWords.push({
        text: wordText,
        visible: word.visible,
        isBold: isWhitespace ? false : isBold
      })
    }
  }
  
  // Second pass: mark first and last in each bold sequence
  for (let i = 0; i < processedWords.length; i++) {
    const word = processedWords[i]
    if (!word) continue
    
    if (word.isBold) {
      // Check if this is the first in sequence
      const isFirst = i === 0 || !processedWords[i - 1]?.isBold
      // Check if this is the last in sequence
      const isLast = i === processedWords.length - 1 || !processedWords[i + 1]?.isBold
      
      if (isFirst) {
        word.isFirstBold = true
      }
      if (isLast) {
        word.isLastBold = true
      }
    }
  }
  
  return processedWords
}

// Render text with bold state (for messages without words array)
const renderTextWithBoldState = (text: string): string => {
  if (!text) return ''
  
  let isBold = false
  let result = ''
  let currentText = ''
  
  // Simple state machine: track bold state and build HTML
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '*' && text[i + 1] === '*') {
      // Found '**' marker
      // Add accumulated text with current bold state
      if (currentText) {
        if (isBold) {
          result += `<strong class="bold-highlight">${escapeHtml(currentText)}</strong>`
        } else {
          result += escapeHtml(currentText)
        }
        currentText = ''
      }
      // Toggle bold state
      isBold = !isBold
      i++ // Skip the second '*'
    } else {
      currentText += text[i]
    }
  }
  
  // Add remaining text
  if (currentText) {
    if (isBold) {
      result += `<strong class="bold-highlight">${escapeHtml(currentText)}</strong>`
    } else {
      result += escapeHtml(currentText)
    }
  }
  
  return result
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
  if (isLoading.value) return
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
    const audio = new Audio(url)
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

const processAudio = async (audioBlob: Blob, mimeType: string) => {
  isLoading.value = true
  
  try {
    // 1) Transcribe audio via backend
    const userMessage = await transcribeWithBackend(audioBlob)
    
    // Add user message to chat history
    chatHistory.value.push({
      role: 'user',
      content: userMessage,
      time: getCurrentTime()
    })
    
    await scrollToBottom()
    
    // Get AI response using streaming chat completion
    const audioBase64 = await blobToBase64(audioBlob)

    // Add placeholder assistant message for streaming (hidden until audio is ready)
    const assistantMessageIndex = chatHistory.value.length
    chatHistory.value.push({
      role: 'assistant',
      content: '',
      time: getCurrentTime(),
      words: [],
      audioReady: false
    })

    // Start a fresh sentence-by-sentence playback session for this turn.
    cancelPlayback()
    const playback: PlaybackSession = {
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
    currentPlayback = playback
    const playerPromise = runSentencePlayer(playback)

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
          curio_app_version: CURIO_APP_VERSION.value
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
                if (pendingText.trim().length > 0) {
                  enqueueSentence(playback, pendingText)
                  pendingText = ''
                  emittedSentenceCount++
                }
                playback.finished = true
                playback.wake?.()
                const concepts = Array.isArray(data.first_time_matched_concepts)
                  ? data.first_time_matched_concepts
                  : []
                if (concepts.length) {
                  emit('firstTimeMatchedConcepts', concepts)
                }
                const assistantMsg = chatHistory.value[assistantMessageIndex]
                if (assistantMsg) {
                  assistantMsg.content = fullText
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
              // Only log if it's not a JSON parse error for empty/incomplete lines
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
            curio_app_version: CURIO_APP_VERSION.value
          })
        })
        
        if (!chatResponse.ok) {
          throw new Error('Chat completion failed')
        }
        
        const chatData = await chatResponse.json()
        fullText = chatData.response
        nextState = chatData.next_state as typeof convState.value
        convState.value = nextState
        
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
        const firstTime = chatData.first_time_matched_concepts
        await generateAndPlayAudioWithPrinterEffect(fullText, assistantMessageIndex, firstTime)
        return
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError)
        throw error // Throw original error
      }
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

  } catch (error) {
    console.error('Error processing audio:', error)
    chatHistory.value.push({
      role: 'assistant',
      content: 'Sorry, I encountered an error. Please try again.',
      time: getCurrentTime()
    })
    await scrollToBottom()
  } finally {
    isLoading.value = false
  }
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
    const audio = new Audio(audioUrl)
    
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
  messageIndex: number,
  firstTimeMatchedConcepts?: string[]
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
    const audio = new Audio(audioUrl)
    
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
    
    // Emit concept bubbles when audio starts playing
    if (firstTimeMatchedConcepts?.length) {
      emit('firstTimeMatchedConcepts', firstTimeMatchedConcepts)
    }
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
    const response = await fetch(`/api/conversations?session_id=${sessionId.value}`)
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
        const restoredMatchedConcepts = messagesData.matched_concepts || []
        
        if (messages.length === 0) {
          return false
        }
        
        // Restore chat history from messages
        // Filter out system messages and only include user and assistant messages
        const greetingText = "Hi, I'm Nova, your friendly science assistant. We are going to explore the scientific mystery in the image together! What do you find odd in this picture?"
        
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

        // Restore concept bubbles from matched concepts in this conversation
        if (restoredMatchedConcepts.length > 0) {
          emit('firstTimeMatchedConcepts', restoredMatchedConcepts)
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
  const greetingText = "Hi, I'm Nova, your friendly science assistant. We are going to explore the scientific mystery in the image together! What do you find odd in this picture?"
  
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
          image_path: props.selectedImagePath || '/imgs/balloon.jpg'
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

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.code === 'Space' && !e.repeat && !isLoading.value) {
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
  await loadAppConfig()
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
@import url('https://fonts.googleapis.com/css2?family=Kodchasan:wght@400;500;600;700&display=swap');

@font-face {
  font-family: 'Krona One';
  src: url('../assets/fonts/KronaOne-Regular.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'Lao Muang Don';
  src: url('../assets/fonts/LaoMuangDon-Regular.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}

/* Design tokens — match learn-together panel */
.chat-container {
  --border-blue: #B9E0EA;
  --header-bg: #C7E8F0;
  --title-color: #3D576A;
  --subtitle-color: #364B5C;
  --user-bubble: #C7E8F0;
  --voice-blue: #79AAFF;
  --text-body: #486174;
  /* Chat window (outer card) — single drop shadow */
  --shadow-chat-window: 0 15px 50px 0 rgba(0, 0, 0, 0.2);
  /* Bubbles, avatar, mic — stacked drop shadows */
  --shadow-layered: 0 8px 10px -6px rgba(0, 0, 0, 0.1), 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  --voice-btn-size: 112px;
}

/* Chat Section */
.chat-container {
  width: 100%;
  max-width: 560px;
  height: 90vh;
  background: #ffffff;
  border: 6px solid var(--border-blue);
  border-radius: 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  z-index: 200;
  box-shadow: var(--shadow-chat-window);
}

.mission-complete-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 13000;
  animation: fadeIn 0.25s ease;
}

.mission-complete-container {
  background: #ffffff;
  border: 4px solid #BFE4F0;
  border-radius: 24px;
  width: min(680px, 92vw);
  box-shadow: var(--shadow-chat-window);
  padding: 26px 26px 22px;
  animation: slideUp 0.25s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.mission-complete-message {
  font-family: 'Kodchasan';
  font-size: 1.4em;
  font-weight: 500;
  color: #3D576A;
  line-height: 1.45;
  margin-bottom: 20px;
  max-width: 100%;
}

.mission-complete-button {
  font-family: 'Kodchasan';
  font-size: 1.05em;
  font-weight: 700;
  padding: 10px 22px;
  border-radius: 999px;
  cursor: pointer;
  border: 2px solid #79AAFF;
  box-shadow: none;
  background: #ffffff;
  color: #000000;
  transition: background 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
}

.mission-complete-button:hover {
  background: #C7E3FF;
  border-color: #79AAFF;
  transform: scale(1.02);
}

.mission-complete-button:active {
  transform: scale(0.98);
}

.room-choice-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 12000;
  animation: fadeIn 0.25s ease;
}

.room-choice-container {
  background: #ffffff;
  border: 4px solid #BFE4F0;
  border-radius: 24px;
  width: min(680px, 92vw);
  box-shadow: var(--shadow-chat-window);
  padding: 26px 26px 22px;
  animation: slideUp 0.25s ease;
}

.room-choice-title {
  font-family: 'Krona One', sans-serif;
  font-size: 1.5em;
  font-weight: 400;
  color: #3D576A;
  margin-bottom: 12px;
}

.room-choice-question {
  font-family: 'Kodchasan';
  font-size: 1.4em;
  font-weight: 500;
  color: #3D576A;
  line-height: 1.45;
  margin-bottom: 18px;
}

.room-choice-actions {
  display: flex;
  gap: 14px;
  justify-content: center;
  flex-wrap: wrap;
}

.room-choice-button {
  font-family: 'Kodchasan';
  font-size: 1.05em;
  font-weight: 700;
  padding: 10px 18px;
  border-radius: 999px;
  cursor: pointer;
  border: 2px solid #79AAFF;
  box-shadow: none;
  background: #ffffff;
  color: #000000;
  transition: background 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
}

.room-choice-button:hover {
  background: #C7E3FF;
  border-color: #79AAFF;
  transform: scale(1.02);
}

.room-choice-button:active {
  transform: scale(0.98);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.chat-panel-header {
  flex-shrink: 0;
  background: var(--header-bg);
  padding: 18px 20px 16px;
  border-bottom: 1px solid var(--border-blue);
}

.chat-panel-title {
  margin: 0;
  font-family: 'Krona One', sans-serif;
  font-size: clamp(1.05rem, 2.8vw, 1.35rem);
  font-weight: 400;
  color: var(--title-color);
  letter-spacing: 0.02em;
  line-height: 1.25;
  text-align: left;
}

.chat-panel-subtitle {
  margin: 8px 0 0;
  font-family: 'Lao Muang Don', sans-serif;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--subtitle-color);
  line-height: 1.35;
  text-align: left;
}

/* Chat Messages */
.chat-messages {
  flex: 1;
  min-height: 0;
  padding: 16px 18px calc(12px + var(--voice-btn-size) / 2);
  overflow-y: auto;
  overflow-x: hidden;
  background: #FAFAFA;
  position: relative;
  z-index: 1;
  transform: translateZ(0);
}

.message {
  margin-bottom: 14px;
  display: flex;
  position: relative;
  z-index: 1;
}

.message-inner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 92%;
}

.message.user .message-inner {
  margin-left: auto;
  flex-direction: row;
  justify-content: flex-end;
}

.message.assistant .message-inner {
  margin-right: auto;
}

.message-avatar {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  object-fit: contain;
  flex-shrink: 0;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 18px;
  position: relative;
  z-index: 10;
  font-family: 'Kodchasan';
  font-size: 1.2rem;
  box-shadow: var(--shadow-layered);
}

.message.user .message-bubble {
  background: var(--user-bubble);
  color: var(--text-body);
  border: none;
  border-bottom-right-radius: 6px;
}

.message.assistant .message-bubble {
  background: #ffffff;
  color: var(--text-body);
  border: 1px solid var(--border-blue);
  border-top-left-radius: 6px;
}

.message-text {
  font-size: 1em;
  line-height: 1.45;
  margin-bottom: 6px;
  text-align: left;
}

.message.user .message-text :deep(.bold-highlight),
.message.user .message-text .bold-highlight {
  font-weight: 700;
  color: #2a4a5c;
  font-family: 'Kodchasan';
  display: inline;
  padding: 0;
  border-radius: 0;
  background-image: linear-gradient(
    transparent 60%,
    rgba(127, 179, 245, 0.45) 60%
  );
}

.message.assistant .message-text :deep(.bold-highlight),
.message.assistant .message-text .bold-highlight {
  font-weight: 700;
  color: #2a4a5c;
  font-family: 'Kodchasan';
  display: inline;
  padding: 0;
  border-radius: 0;
  background-image: linear-gradient(
    transparent 60%,
    rgba(127, 179, 245, 0.4) 60%
  );
}

.word-visible {
  opacity: 1;
  transition: opacity 0.1s ease-in;
}

.word-hidden {
  opacity: 0;
}

.message-bubble {
  transition: opacity 0.3s ease-in;
}

.message-time {
  font-family: 'Kodchasan';
  font-size: 0.85rem;
  opacity: 0.55;
  color: var(--text-body);
  text-align: right;
}

/* Welcome Message */
.welcome-message {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.welcome-bubble {
  background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
  padding: 20px;
  border-radius: 20px;
  text-align: center;
  border: 3px solid #ff6b9d;
}

.welcome-text {
  font-size: 1.1em;
  color: #333;
  line-height: 1.5;
}

/* Push-to-Talk Input — mic sits half above / half inside this bar */
.chat-input-area {
  flex-shrink: 0;
  padding: 0 18px 8px;
  position: relative;
  z-index: 4;
  background: #F2F7F9;
  border-top: 4.5px solid var(--border-blue);
}

.voice-input-container {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: calc(-0.5 * var(--voice-btn-size));
  margin-bottom: 2px;
}

.voice-hint {
  margin: 4px 0 0;
  font-family: 'Lao Muang Don', sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  color: rgba(61, 87, 106, 0.72);
  text-align: center;
  line-height: 1.35;
}

.voice-input-button {
  color: #ffffff;
  font-size: 2em;
  width: var(--voice-btn-size);
  height: var(--voice-btn-size);
  min-width: var(--voice-btn-size);
  min-height: var(--voice-btn-size);
  padding: 0;
  border-radius: 50%;
  border: 2px solid rgba(191, 228, 240, 0.85);
  background: #79AAFF;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease, border-color 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-layered);
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
  aspect-ratio: 1;
}

.voice-input-button:hover:not(:disabled) {
  transform: scale(1.04);
  filter: brightness(1.03);
  border-color: #568E9C;
}

.voice-input-button:active {
  transform: scale(0.96);
}

.voice-input-button.recording {
  background: #3C69B8;
  border-color: rgba(232, 120, 154, 0.55);
  animation: pulse 1.5s infinite;
  box-shadow: var(--shadow-layered);
}


.voice-input-button.loading {
  background: linear-gradient(180deg, #c5d8e8 0%, #9eb8d4 100%);
  border-color: var(--border-blue);
  box-shadow: var(--shadow-layered);
  cursor: not-allowed;
}


.voice-input-button:disabled {
  cursor: not-allowed;
  transform: none;
}

.voice-icon {
  font-size: 3.25rem;
  line-height: 1;
  flex-shrink: 0;
  color: currentColor;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.recording-icon {
  animation: bounce 0.6s infinite alternate;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 8px 10px -6px rgba(0, 0, 0, 0.08), 0 20px 25px -5px rgba(0, 0, 0, 0.08);
  }
  50% {
    box-shadow: 0 8px 12px -6px rgba(0, 0, 0, 0.14), 0 20px 30px -5px rgba(0, 0, 0, 0.14);
  }
}

@keyframes bounce {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(-10px);
  }
}

/* Responsive Design */
@media (max-width: 1024px) {
  .chat-container {
    --voice-btn-size: 100px;
  }

  .chat-messages {
    padding: 14px 14px calc(10px + var(--voice-btn-size) / 2);
  }
  
  .voice-icon {
    font-size: 2.875rem;
  }
}

@media (max-width: 768px) {
  .chat-container {
    height: min(78vh, 720px);
    max-width: 100%;
    border-radius: 20px;
    --voice-btn-size: 96px;
  }

  .chat-panel-header {
    padding: 14px 16px 12px;
  }

  .chat-messages {
    padding: 12px 12px calc(8px + var(--voice-btn-size) / 2);
  }
  
  .message-bubble {
    padding: 10px 14px;
  }
  
  .message.user .message-bubble,
  .message.assistant .message-bubble {
    font-size: 1.12rem;
  }
  
  .message-text {
    font-size: 1.2em;
  }
  
  .message-time {
    font-size: 0.7em;
  }
  
  .chat-input-area {
    padding: 0 14px 6px;
  }
  
  .voice-icon {
    font-size: 2.75rem;
  }

  .voice-hint {
    font-size: 0.78rem;
  }
}

@media (max-width: 480px) {
  .chat-container {
    height: min(82vh, 680px);
    border-radius: 18px;
    --voice-btn-size: 88px;
  }

  .chat-messages {
    padding: 10px 10px calc(6px + var(--voice-btn-size) / 2);
  }
  
  .message {
    margin-bottom: 12px;
  }
  
  .message-bubble {
    padding: 8px 12px;
    border-radius: 14px;
  }
  
  .message.user .message-bubble,
  .message.assistant .message-bubble {
    font-size: 1.08rem;
  }
  
  .message-text {
    font-size: 1em;
  }
  
  .message-time {
    font-size: 0.68em;
  }
  
  .chat-input-area {
    padding: 0 12px 6px;
  }
  
  .voice-icon {
    font-size: 2.5rem;
  }

  .message-avatar {
    width: 36px;
    height: 36px;
  }
}

/* Scrollbar Styling */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: #eef6f9;
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #c5dde8;
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #a8ccd9;
}
</style>
