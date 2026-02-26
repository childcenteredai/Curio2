<template>
  <div class="chat-container">
    <!-- Character image - inside chat-container but outside chat-messages -->
    <div class="curio-character">
      <img src="/imgs/curio-character.png" alt="Curio" class="curio-character-image">
    </div>

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
          <div class="message-time">{{ msg.time }}</div>
        </div>
      </div>
    </div>

    <!-- Push-to-talk area -->
    <div class="chat-input-area">
      <div class="push-to-talk-container">
        <button 
          @mousedown="handleMouseDown"
          @mouseup="handleMouseUp"
          @mouseleave="handleMouseLeave"
          :disabled="isLoading"
          :class="`push-to-talk-button ${isRecording ? 'recording' : ''} ${isLoading ? 'loading' : ''}`"
        >
          <div class="button-content">
            <span v-if="isLoading" class="loading-icon">⏳</span>
            <span v-else-if="isRecording" class="recording-icon">🎤</span>
            <span v-else class="mic-icon">🎤</span>
            <div class="button-text">
              {{ isLoading ? 'Processing...' : isRecording ? 'Recording...' : 'Hold to Speak' }}
            </div>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
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
        // Even count: opening and closing in same word, state doesn't change
        wordIsBold = isBold
      }
      
      processedWords.push({
        text: wordText,
        visible: word.visible,
        isBold: wordIsBold
      })
    } else {
      // No marker, use current bold state (including for whitespace)
      processedWords.push({
        text: wordText,
        visible: word.visible,
        isBold: isBold
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

const handleMouseDown = async () => {
  if (!isRecording.value && !isLoading.value) {
    await startRecording()
  }
}

const handleMouseUp = () => {
  if (isRecording.value) {
    stopRecording()
  }
}

const handleMouseLeave = () => {
  if (isRecording.value) {
    stopRecording()
  }
}

const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
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
    
    let fullText = ''
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
          user_audio_mime_type: mimeType
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
      let lastScrollTime = 0
      const scrollThrottle = 100 // Throttle scrolling to every 100ms during streaming
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
                fullText += data.content || ''
                // Update content for display (will be hidden until audio plays)
                const assistantMsg = chatHistory.value[assistantMessageIndex]
                if (assistantMsg) {
                  assistantMsg.content = fullText
                }
                // Auto-scroll during streaming (throttled)
                const now = Date.now()
                if (now - lastScrollTime >= scrollThrottle) {
                  await scrollToBottom()
                  lastScrollTime = now
                }
              } else if (data.type === 'done') {
                fullText = data.response || fullText
                nextState = data.next_state as typeof convState.value
                convState.value = nextState
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
            user_audio_mime_type: mimeType
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
        await generateAndPlayAudioWithPrinterEffect(fullText, assistantMessageIndex)
        return
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError)
        throw error // Throw original error
      }
    }
    
    // Check if we have any text to display
    if (!fullText || fullText.trim().length === 0) {
      console.error('No text received from stream')
      const assistantMsg = chatHistory.value[assistantMessageIndex]
      if (assistantMsg) {
        assistantMsg.content = 'Sorry, I encountered an error generating a response. Please try again.'
        assistantMsg.audioReady = true // Show message even without audio
      }
      await scrollToBottom()
      return
    }
    
    // Split text into words for printer effect
    const words = fullText.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
      text: w,
      visible: false
    }))
    
    const assistantMsg = chatHistory.value[assistantMessageIndex]
    if (assistantMsg) {
      assistantMsg.words = words
      assistantMsg.content = fullText
      // Keep audioReady as false - will be set to true when audio is ready
    }
    
    await scrollToBottom()
    
    // Generate and play audio with printer effect
    await generateAndPlayAudioWithPrinterEffect(fullText, assistantMessageIndex)
    
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
      URL.revokeObjectURL(audioUrl)
      if (currentAudio === audio) {
        currentAudio = null
      }
    }
    
    await audio.play()
  } catch (error) {
    console.error('Error playing audio:', error)
  }
}

const generateAndPlayAudioWithPrinterEffect = async (text: string, messageIndex: number) => {
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
        // No words to reveal, just play audio
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
      }
    }
    
    setupPrinterEffect()
    
    await audio.play()
  } catch (error) {
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
        
        if (messages.length === 0) {
          return false
        }
        
        // Restore chat history from messages
        // Filter out system messages and only include user and assistant messages
        const greetingText = "Hi, I'm Curio, your friendly science assistant. We are going to explore the scientific mystery in the image together! What do you find odd in this picture?"
        
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
  const greetingText = "Hi, I'm Curio, your friendly science assistant. We are going to explore the scientific mystery in the image together! What do you find odd in this picture?"
  
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
  
  // Create a new conversation ID but keep the same session ID
  conversationId.value = crypto.randomUUID()
  
  // Clear the chat history
  chatHistory.value = []
  convState.value = 'greet'
  
  // Generate initial greeting for the new conversation
  await generateInitialGreeting()
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.code === 'Space' && !isRecording.value && !isLoading.value) {
    e.preventDefault()
    startRecording()
  }
}

const handleKeyUp = (e: KeyboardEvent) => {
  if (e.code === 'Space' && isRecording.value) {
    e.preventDefault()
    stopRecording()
  }
}

// Watch for chat history changes to update scroll state
watch(chatHistory, async () => {
  await nextTick()
  updateScrollState()
}, { deep: true })

// Watch for image path changes and reload conversation if needed
watch(() => props.selectedImagePath, async (newPath, oldPath) => {
  // If image path changes, always reload conversation for the new image
  if (newPath !== oldPath) {
    // Stop any playing audio first
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
  document.addEventListener('keyup', handleKeyUp)
  
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
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('keyup', handleKeyUp)
  
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
  
  // Stop any playing audio
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
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

/* Chat Section */
.chat-container {
  width: 100%;
  max-width: 500px;
  height: 80vh;
  background: #FFEC99;
  border: 8px solid white;
  border-radius: 40px;
  flex-direction: column;
  overflow: visible; /* Allow character image to overflow */
  position: relative;
  z-index: 200; /* Higher z-index to ensure messages are above character */
  padding: 10px;
}

.curio-character{
  width: 20vw;
  height: fit-content;
  position: absolute; /* Absolute positioning relative to chat-container */
  left: -12vw;
  top: -12vh;
  z-index: 0; /* Lower z-index - character below messages */
  pointer-events: none; /* Allow clicks to pass through to messages */
  overflow: visible; /* Ensure image can overflow */
}

.curio-character-image{
  width: 20vw;
  height: fit-content;
  object-fit: contain;
  pointer-events: auto; /* Re-enable pointer events for the image itself */
}

.chat-title {
  margin: 0;
  font-size: 1.8em;
  font-weight: bold;
}

.chat-subtitle {
  margin-top: 5px;
  opacity: 0.9;
  font-size: 1em;
}

/* Chat Messages */
.chat-messages {
  flex: 1;
  padding: 40px 20px 40px 60px;
  height: 70vh;
  overflow-y: auto;
  overflow-x: hidden; /* Standard overflow for scrollable container */
  border-radius: 40px;
  position: relative;
  z-index: 300; /* Highest layer - messages container above character */
  transform: translateZ(0); /* Force hardware acceleration and new stacking context */
}


.message {
  margin-bottom: 15px;
  display: flex;
  position: relative;
  z-index: 1; /* Ensure messages are in the stacking context */
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-bubble {
  /* max-width: 80%; */
  padding: 12px 16px;
  border-radius: 20px;
  position: relative;
  z-index: 10; /* Higher z-index to ensure visibility above character */
}

.message.user .message-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-family: 'Roboto';
  font-size: 1.3em;
  border: 3px solid white;
  border-bottom-right-radius: 0px;
}

.message.assistant .message-bubble {
  background: #008CBB;
  color: #ffffff;
  font-family: 'Roboto';
  font-size: 1.3em;
  border: 3px solid white;
  border-top-left-radius: 0px;
  position: relative;
}

.message-text {
  font-size: 1em;
  line-height: 1.4;
  margin-bottom: 5px;
  text-align: left;
}

.message-text :deep(.bold-highlight),
.message-text .bold-highlight {
  font-weight: 700;
  color: #FFE600;
  background: rgba(255, 230, 0, 0.2);
  padding: 1px 0;
  font-family: 'Roboto', sans-serif;
  display: inline;
}

.message-text :deep(.bold-highlight.bold-first),
.message-text .bold-highlight.bold-first {
  border-top-left-radius: 3px;
  border-bottom-left-radius: 3px;
}

.message-text :deep(.bold-highlight.bold-last),
.message-text .bold-highlight.bold-last {
  border-top-right-radius: 3px;
  border-bottom-right-radius: 3px;
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
  font-size: 0.75em;
  opacity: 0.7;
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

/* Push-to-Talk Input */
.chat-input-area {
  padding: 20px;
  position: relative;
  z-index: 200; /* Same as messages - above character */
}

.push-to-talk-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

.push-to-talk-button {
  font-family: 'Peachy Kink';
  color: #FFE600;
  font-size: 2em;
  width: min(90%, 380px);
  height: 100px;
  border: none;
  border-radius: 100px;
  background: #686DF4;
  border: 6px solid #D4C5FA;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 0 0 #3F4296;
  position: relative;
  overflow: hidden;
}

.push-to-talk-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 0 0 #3F4296;
}

.push-to-talk-button:active {
  transform: scale(0.95);
}

.push-to-talk-button.recording {
  background: linear-gradient(135deg, #ff6b9d 0%, #c44569 100%);
  border: 6px solid #ffbdcb;
  animation: pulse 1.5s infinite;
  box-shadow: 0 6px 0 0 #d73475;
}

.push-to-talk-button.loading {
  background: linear-gradient(135deg, #ffa726 0%, #ff7043 100%);
  border: 6px solid #fdc77b;
  box-shadow: 0 6px 0 0 #ffa323;
  cursor: not-allowed;
}

.push-to-talk-button:disabled {
  cursor: not-allowed;
  transform: none;
}

.button-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.mic-icon, .recording-icon, .loading-icon {
  font-size: 1.5em;
  margin-bottom: 10px;
  display: block;
  margin-right: 10px;
}

.recording-icon {
  animation: bounce 0.6s infinite alternate;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

.button-text {
  font-size: 1.2em;
  font-weight: bold;
  margin-bottom: 5px;
}

.keyboard-hint {
  font-size: 0.9em;
  opacity: 0.8;
  font-style: italic;
}

@keyframes pulse {
  0% {
    box-shadow: 0 8px 25px rgba(255, 107, 157, 0.4);
  }
  50% {
    box-shadow: 0 8px 35px rgba(255, 107, 157, 0.6);
  }
  100% {
    box-shadow: 0 8px 25px rgba(255, 107, 157, 0.4);
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

/* .loading {
  animation: spin 1s linear infinite;
} */

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Responsive Design */
@media (max-width: 1024px) {
  .curio-character {
    width: 15vw;
    left: -8vw;
    top: -8vh;
  }
  
  .curio-character-image {
    width: 15vw;
  }
  
  .chat-messages {
    padding: 30px 15px 30px 50px;
  }
  
  .push-to-talk-button {
    width: 320px;
    height: 90px;
    font-size: 1.8em;
  }
  
  .button-text {
    font-size: 1.1em;
  }
}

@media (max-width: 768px) {
  .chat-container {
    height: 70vh;
    max-width: 100%;
    padding: 8px;
    border-width: 4px;
    border-radius: 30px;
  }
  
  .curio-character {
    width: 25vw;
    left: -10vw;
    top: -6vh;
  }
  
  .curio-character-image {
    width: 25vw;
  }
  
  .chat-messages {
    padding: 30px 15px 30px 40px;
    height: 60vh;
  }
  
  .message-bubble {
    padding: 10px 14px;
  }
  
  .message.user .message-bubble,
  .message.assistant .message-bubble {
    font-size: 1.2em;
    border-width: 4px;
  }
  
  .message-text {
    font-size: 0.9em;
  }
  
  .message-time {
    font-size: 0.7em;
  }
  
  .chat-input-area {
    padding: 15px;
  }
  
  .push-to-talk-button {
    width: min(90%, 280px);
    height: 80px;
    font-size: 1.5em;
    border-width: 4px;
  }
  
  .button-content {
    flex-direction: column;
    gap: 5px;
  }
  
  .mic-icon, .recording-icon, .loading-icon {
    font-size: 1.2em;
    margin-right: 0;
    margin-bottom: 0;
  }
  
  .button-text {
    font-size: 0.9em;
    margin-bottom: 0;
  }
  
  .keyboard-hint {
    font-size: 0.75em;
  }
}

@media (max-width: 480px) {
  .chat-container {
    height: 75vh;
    padding: 5px;
    border-width: 3px;
    border-radius: 25px;
  }
  
  .curio-character {
    width: 30vw;
    left: -8vw;
    top: -4vh;
  }
  
  .curio-character-image {
    width: 30vw;
  }
  
  .chat-messages {
    padding: 25px 10px 25px 35px;
    height: 65vh;
    border-radius: 25px;
  }
  
  .message {
    margin-bottom: 12px;
  }
  
  .message-bubble {
    padding: 8px 12px;
    border-radius: 15px;
  }
  
  .message.user .message-bubble,
  .message.assistant .message-bubble {
    font-size: 1em;
    border-width: 3px;
  }
  
  .message-text {
    font-size: 0.85em;
  }
  
  .message-time {
    font-size: 0.65em;
  }
  
  .chat-input-area {
    padding: 10px;
  }
  
  .push-to-talk-button {
    width: min(95%, 250px);
    height: 70px;
    font-size: 1.3em;
    border-width: 3px;
    border-radius: 80px;
  }
  
  .mic-icon, .recording-icon, .loading-icon {
    font-size: 1em;
  }
  
  .button-text {
    font-size: 0.8em;
  }
}

/* Scrollbar Styling */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
}
</style>
