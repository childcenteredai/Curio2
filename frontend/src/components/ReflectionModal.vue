<template>
  <div v-if="isVisible" class="modal-overlay" @click.self="handleOverlayClick">
    <div class="modal-container">
      <div class="modal-header">
        <h2 class="modal-title">Reflection</h2>
        <button class="close-button" @click="closeModal" aria-label="Close">×</button>
      </div>
      
      <div class="modal-content">
        <!-- Summary/Response Display -->
        <div class="summary-section">
          <div class="summary-text">
            <template v-if="hasBulletPoints">
              <!-- Display opening sentence and bullet points with printer effect -->
              <template v-if="openingSentenceWords && openingSentenceWords.length > 0">
                <div class="opening-sentence">
                  <span 
                    v-for="(word, wordIndex) in renderWordsWithBoldState(openingSentenceWords)" 
                    :key="`opening-${wordIndex}`"
                    :class="{ 
                      'word-visible': word.visible, 
                      'word-hidden': !word.visible,
                      'bold-highlight': word.isBold,
                      'bold-first': word.isFirstBold,
                      'bold-last': word.isLastBold
                    }"
                    v-html="escapeHtml(word.text)"
                  ></span>
                </div>
              </template>
              <ul class="summary-bullet-list" v-if="bulletPointsWords && bulletPointsWords.length > 0">
                <li 
                  v-for="(bulletPoint, bulletIndex) in bulletPointsWords" 
                  :key="`bullet-${bulletIndex}`"
                  class="bullet-point-item"
                >
                  <span 
                    v-for="(word, wordIndex) in renderWordsWithBoldState(bulletPoint.words)" 
                    :key="`bullet-${bulletIndex}-word-${wordIndex}`"
                    :class="{ 
                      'word-visible': word.visible, 
                      'word-hidden': !word.visible,
                      'bold-highlight': word.isBold,
                      'bold-first': word.isFirstBold,
                      'bold-last': word.isLastBold
                    }"
                    v-html="escapeHtml(word.text)"
                  ></span>
                </li>
              </ul>
            </template>
            <template v-else-if="summaryWords && summaryWords.length > 0">
              <span 
                v-for="(word, wordIndex) in renderWordsWithBoldState(summaryWords)" 
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
            <span v-else v-html="renderTextWithBoldState(summary)"></span>
          </div>
        </div>
        
        <!-- Question 1: Likert Scale -->
        <div class="question-section" v-show="showQuestion1">
          <p class="question-text">
            <template v-if="question1Words && question1Words.length > 0">
              <span 
                v-for="(word, wordIndex) in question1Words" 
                :key="wordIndex"
                :class="{ 
                  'word-visible': word.visible, 
                  'word-hidden': !word.visible
                }"
                v-html="escapeHtml(word.text)"
              ></span>
            </template>
            <span v-else>Do you think we are getting closer to explaining why this happens?</span>
          </p>
          <div class="likert-container" v-show="question1AudioFinished">
            <div class="likert-labels">
              <span 
                :class="['likert-label', { 'active': likertValue === 1 }]"
              >Not at all</span>
              <span 
                :class="['likert-label', { 'active': likertValue === 2 }]"
              >A little</span>
              <span 
                :class="['likert-label', { 'active': likertValue === 3 }]"
              >Somewhat</span>
              <span 
                :class="['likert-label', { 'active': likertValue === 4 }]"
              >Very much</span>
            </div>
            <input 
              type="range" 
              min="1" 
              max="4" 
              step="1" 
              v-model.number="likertValue"
              class="likert-slider"
              @input="handleLikertChange"
            />
          </div>
        </div>
        
        <!-- Question 2: Voice Input -->
        <div class="question-section" v-show="showQuestion2">
          <p class="question-text">
            <template v-if="question2Words && question2Words.length > 0">
              <span 
                v-for="(word, wordIndex) in question2Words" 
                :key="wordIndex"
                :class="{ 
                  'word-visible': word.visible, 
                  'word-hidden': !word.visible
                }"
                v-html="escapeHtml(word.text)"
              ></span>
            </template>
            <span v-else>Is everything clear? Is there anything you are still unsure about?</span>
          </p>
          <div class="voice-input-container" v-show="question2AudioFinished">
            <button 
              id="modal-voice-button"
              @mousedown="handleMouseDown"
              @mouseup="handleMouseUp"
              @mouseleave="handleMouseLeave"
              :disabled="isLoading"
              :class="`voice-input-button ${isRecording ? 'recording' : ''} ${isLoading ? 'loading' : ''}`"
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted, computed } from 'vue'

const props = defineProps<{
  isVisible: boolean
  summary: string
  summaryWords?: Array<{text: string, visible: boolean}>
}>()

const emit = defineEmits<{
  close: []
  likertResponse: [value: number]
  voiceResponse: [text: string]
  summaryAudioFinished: []
}>()

const likertValue = ref(2) // Default to middle value
const isRecording = ref(false)
const isLoading = ref(false)
const summaryWords = ref<Array<{text: string, visible: boolean, isBold?: boolean, isFirstBold?: boolean, isLastBold?: boolean}>>([])
const showQuestion1 = ref(false)
const showQuestion2 = ref(false)
const question1AudioFinished = ref(false)
const question2AudioFinished = ref(false)
const question1Words = ref<Array<{text: string, visible: boolean}>>([])
const question2Words = ref<Array<{text: string, visible: boolean}>>([])
const openingSentenceWords = ref<Array<{text: string, visible: boolean, isBold?: boolean, isFirstBold?: boolean, isLastBold?: boolean}>>([])
const bulletPointsWords = ref<Array<{words: Array<{text: string, visible: boolean, isBold?: boolean, isFirstBold?: boolean, isLastBold?: boolean}>}>>([])
const defaultOpeningSentence = ref('')

// Get a random opening sentence
const getRandomOpeningSentence = (): string => {
  const options: string[] = [
    "Here are the pieces of the puzzles of what we have explored so far!",
    "Let's think about what we have explored so far!"
  ]
  const index = Math.floor(Math.random() * options.length)
  return options[index] ?? options[0] ?? ""
}

// Check if summary contains bullet points
const hasBulletPoints = computed(() => {
  if (!props.summary) return false
  const lines = props.summary.split('\n')
  return lines.some(line => line.trim().startsWith('- '))
})

// Parse summary into opening sentence and bullet points
const parseSummaryWithBulletPoints = (summary: string) => {
  if (!summary) return { openingSentence: '', bulletPoints: [] }
  
  const lines = summary.split('\n').map(line => line.trim()).filter(line => line.length > 0)
  let bulletPoints: string[] = []
  let openingSentence = ''
  
  // Collect all non-bullet lines as opening sentence, and all bullet lines as bullet points
  const openingLines: string[] = []
  let foundFirstBullet = false
  
  for (const line of lines) {
    if (line && line.startsWith('- ')) {
      // This is a bullet point
      foundFirstBullet = true
      const bulletText = line.substring(2).trim()
      if (bulletText.length > 0) {
        bulletPoints.push(bulletText)
      }
    } else if (line && !foundFirstBullet) {
      // This is part of the opening sentence (only before first bullet)
      openingLines.push(line)
    } else if (line && foundFirstBullet) {
      // Non-bullet line after bullets found - might be continuation or error, ignore for now
      // Could be handled differently if needed
    }
  }
  
  // Join all opening lines into one sentence
  openingSentence = openingLines.join(' ').trim()
  
  return { openingSentence, bulletPoints }
}

// Audio recording
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []
let recorderMimeType = ''
let currentAudio: HTMLAudioElement | null = null

// Helper to escape HTML
const escapeHtml = (str: string): string => {
  if (!str) return ''
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

// Render words with bold state (similar to Conversation.vue)
const renderWordsWithBoldState = (words: Array<{text: string, visible: boolean}>): Array<{text: string, visible: boolean, isBold: boolean, isFirstBold?: boolean, isLastBold?: boolean}> => {
  if (!words) return []
  
  let isBold = false
  const processedWords: Array<{text: string, visible: boolean, isBold: boolean, isFirstBold?: boolean, isLastBold?: boolean}> = []
  
  // First pass: mark bold words
  for (const word of words) {
    let wordText = word.text
    
    // Check if this word contains '**'
    if (wordText.includes('**')) {
      const markerCount = (wordText.match(/\*\*/g) || []).length
      wordText = wordText.replace(/\*\*/g, '')
      
      let wordIsBold: boolean
      
      if (markerCount % 2 === 1) {
        if (!isBold) {
          isBold = true
          wordIsBold = true
        } else {
          wordIsBold = true
          isBold = false
        }
      } else {
        wordIsBold = isBold
      }
      
      processedWords.push({
        text: wordText,
        visible: word.visible,
        isBold: wordIsBold
      })
    } else {
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
      const isFirst = i === 0 || !processedWords[i - 1]?.isBold
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

// Render text with bold state and bullet points (for messages without words array)
const renderTextWithBoldState = (text: string): string => {
  if (!text) return ''
  
  // Check if text contains bullet points (lines starting with "- ")
  const lines = text.split('\n')
  const hasBulletPoints = lines.some(line => line.trim().startsWith('- '))
  
  if (hasBulletPoints) {
    // Process as bullet points
    let result = '<ul class="summary-bullet-list">'
    
    for (const line of lines) {
      const trimmedLine = line.trim()
      if (trimmedLine.startsWith('- ')) {
        // Extract content after "- "
        const content = trimmedLine.substring(2)
        // Process bold markers in content
        const processedContent = processBoldInText(content)
        result += `<li>${processedContent}</li>`
      } else if (trimmedLine.length > 0) {
        // Non-bullet line, process normally
        const processedContent = processBoldInText(trimmedLine)
        result += `<li>${processedContent}</li>`
      }
    }
    
    result += '</ul>'
    return result
  } else {
    // Process as regular text with bold markers
    return processBoldInText(text)
  }
}

// Helper function to process bold markers in text
const processBoldInText = (text: string): string => {
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

const handleLikertChange = (event?: Event) => {
  // Ensure likertValue is a number
  if (event && event.target) {
    const target = event.target as HTMLInputElement
    likertValue.value = parseInt(target.value, 10)
  }
  emit('likertResponse', likertValue.value)
}

const closeModal = () => {
  emit('close')
}

const handleOverlayClick = () => {
  // Don't close on overlay click - user must interact with the modal
}

const handleMouseDown = async (event: MouseEvent) => {
  event.preventDefault()
  event.stopPropagation()
  if (!isRecording.value && !isLoading.value) {
    await startRecording()
  }
}

const handleMouseUp = (event: MouseEvent) => {
  event.preventDefault()
  event.stopPropagation()
  if (isRecording.value) {
    stopRecording()
  }
}

const handleMouseLeave = (event: MouseEvent) => {
  event.preventDefault()
  event.stopPropagation()
  if (isRecording.value) {
    stopRecording()
  }
}

// Keyboard event handlers for spacebar
const handleKeyDown = async (event: KeyboardEvent) => {
  // Only handle spacebar when modal is visible, question 2 is shown, and not loading
  if (event.code === 'Space' && props.isVisible && showQuestion2.value && question2AudioFinished.value && !isLoading.value) {
    // Prevent default spacebar behavior (scrolling)
    event.preventDefault()
    event.stopPropagation()
    
    // Only start recording if not already recording
    if (!isRecording.value) {
      await startRecording()
    }
  }
}

const handleKeyUp = (event: KeyboardEvent) => {
  // Only handle spacebar when modal is visible and recording
  if (event.code === 'Space' && props.isVisible && isRecording.value) {
    event.preventDefault()
    event.stopPropagation()
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
      await processAudio(audioBlob)
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

const processAudio = async (audioBlob: Blob) => {
  isLoading.value = true
  
  try {
    // Transcribe audio via backend
    const userMessage = await transcribeWithBackend(audioBlob)
    
    // Emit the voice response to parent - don't close modal here
    // Modal will close when reply is generated
    emit('voiceResponse', userMessage)
    // Keep isLoading true - parent will handle the response generation
    // and set it to false when done
  } catch (error) {
    console.error('Error processing audio:', error)
    isLoading.value = false
  }
}

// Note: All audio is now played with printer effect using playTextWithPrinterEffect

// Play text with printer effect
const playTextWithPrinterEffect = async (text: string, words: Array<{text: string, visible: boolean}>): Promise<void> => {
  try {
    if (!text || typeof text !== 'string' || text.trim().length === 0) {
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
      console.error('Speech generation failed:', response.status)
      return
    }
    
    const audioBlob = await response.blob()
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    
    currentAudio = audio
    
    const setupPrinterEffect = () => {
      const onReady = () => {
        startPrinterEffect()
      }
      
      if (audio.readyState >= 2) {
        onReady()
      } else {
        audio.addEventListener('canplay', onReady, { once: true })
        audio.addEventListener('loadedmetadata', () => {
          if (audio.readyState >= 2) {
            onReady()
          }
        }, { once: true })
      }
    }
    
    const startPrinterEffect = () => {
      const duration = audio.duration
      if (!words || words.length === 0) return
      
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
      const updateInterval = setInterval(() => {
        if (!audio || audio.paused || audio.ended) {
          clearInterval(updateInterval)
          return
        }
        
        const currentAudioTime = audio.currentTime || 0
        
        // Reveal words that should be visible at current time
        while (currentWordIndex < wordTimings.length) {
          const timing = wordTimings[currentWordIndex]
          if (!timing || currentAudioTime < timing.time) break
          const wordIdx = timing.wordIndex
          if (wordIdx !== undefined && words && words[wordIdx]) {
            words[wordIdx].visible = true
          }
          currentWordIndex++
        }
      }, 50)
      
      // Set up audio event handlers
      audio.onended = () => {
        clearInterval(updateInterval)
        // Make sure all words are visible at the end
        if (words) {
          words.forEach(word => word.visible = true)
        }
        URL.revokeObjectURL(audioUrl)
        if (currentAudio === audio) {
          currentAudio = null
        }
        // Resolve the promise
        if (resolvePromise) {
          resolvePromise()
        }
      }
      
      audio.onerror = () => {
        clearInterval(updateInterval)
        // Make sure all words are visible even on error
        if (words) {
          words.forEach(word => word.visible = true)
        }
        URL.revokeObjectURL(audioUrl)
        if (currentAudio === audio) {
          currentAudio = null
        }
        // Resolve the promise even on error
        if (resolvePromise) {
          resolvePromise()
        }
      }
    }
    
    let resolvePromise: (() => void) | null = null
    const playPromise = new Promise<void>((resolve) => {
      resolvePromise = resolve
      setupPrinterEffect()
      
      audio.play().catch(err => {
        console.error('Error playing audio:', err)
        if (resolvePromise) {
          resolvePromise()
        }
      })
    })
    
    return playPromise
  } catch (error) {
    console.error('Error playing text with printer effect:', error)
  }
}

// Play the two fixed questions with printer effect
const playFixedQuestions = async () => {
  const question1 = "Do you think we are getting closer to explaining why this happens?"
  const question2 = "Is everything clear? Is there anything you are still unsure about?"
  
  // Initialize words for question 1
  question1Words.value = question1.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
    text: w,
    visible: false
  }))
  showQuestion1.value = true
  
  // Play first question with printer effect
  await playTextWithPrinterEffect(question1, question1Words.value)
  question1AudioFinished.value = true
  
  // Small delay between questions
  await new Promise(resolve => setTimeout(resolve, 500))
  
  // Initialize words for question 2
  question2Words.value = question2.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
    text: w,
    visible: false
  }))
  showQuestion2.value = true
  
  // Play second question with printer effect
  await playTextWithPrinterEffect(question2, question2Words.value)
  question2AudioFinished.value = true
}

// Track if summary audio has finished (from Conversation.vue)
const summaryAudioFinished = ref(false)

// Method to be called when summary audio finishes (from parent) - no longer needed
// We now play summary audio directly in the modal
const onSummaryAudioFinished = () => {
  // This method is kept for compatibility but summary is now played in modal
}

// Expose method for parent to call when summary audio finishes
defineExpose({
  onSummaryAudioFinished
})

// Play summary with printer effect in modal
const playSummaryWithPrinterEffect = async () => {
  if (!props.summary) return
  
  // If summary has bullet points, play opening sentence and bullet points separately
  if (hasBulletPoints.value) {
    const { bulletPoints } = parseSummaryWithBulletPoints(props.summary)
    
    // Play hardcoded opening sentence with printer effect (always play it)
    if (defaultOpeningSentence.value && openingSentenceWords.value.length > 0) {
      // Ensure all words are hidden before playing
      openingSentenceWords.value.forEach(word => {
        word.visible = false
      })
      
      // Play opening sentence with printer effect (TTS)
      await playTextWithPrinterEffect(defaultOpeningSentence.value, openingSentenceWords.value)
      
      // Small delay before bullet points
      await new Promise(resolve => setTimeout(resolve, 300))
    }
    
    // Play each bullet point with printer effect (if words are initialized)
    if (bulletPointsWords.value.length > 0) {
      for (let i = 0; i < bulletPointsWords.value.length; i++) {
        const bulletPoint = bulletPointsWords.value[i]
        if (!bulletPoint || !bulletPoint.words || bulletPoint.words.length === 0) continue
        
        const bulletText = bulletPoints[i]
        if (!bulletText) continue
        
        // Ensure all words are hidden before playing
        bulletPoint.words.forEach(word => {
          word.visible = false
        })
        
        // Play this bullet point with printer effect (TTS)
        await playTextWithPrinterEffect(bulletText, bulletPoint.words)
        
        // Small delay between bullet points (except for the last one)
        if (i < bulletPointsWords.value.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 200))
        }
      }
    }
    
    return
  }
  
  // Regular summary without bullet points
  // Initialize words array - start with all invisible
  if (props.summaryWords && props.summaryWords.length > 0) {
    summaryWords.value = props.summaryWords.map(w => ({ ...w, visible: false }))
  } else if (props.summary) {
    summaryWords.value = props.summary.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
      text: w,
      visible: false
    }))
  } else {
    return // No summary to play
  }
  
  await playTextWithPrinterEffect(props.summary, summaryWords.value)
}

// Watch for modal visibility and props changes
watch(() => props.isVisible, async (newVal) => {
  if (newVal) {
    likertValue.value = 2 // Reset to default
    summaryAudioFinished.value = false
    showQuestion1.value = false
    showQuestion2.value = false
    question1AudioFinished.value = false
    question2AudioFinished.value = false
    question1Words.value = []
    question2Words.value = []
    openingSentenceWords.value = []
    bulletPointsWords.value = []
    
    // Initialize summaryWords immediately when modal opens
    if (hasBulletPoints.value && props.summary) {
      // Parse bullet points from summary
      const { bulletPoints } = parseSummaryWithBulletPoints(props.summary)
      
      // Use hardcoded opening sentence (randomly selected)
      defaultOpeningSentence.value = getRandomOpeningSentence()
      
      // Initialize opening sentence words
      openingSentenceWords.value = defaultOpeningSentence.value.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
        text: w,
        visible: false
      }))
      
      // Initialize bullet points words
      bulletPointsWords.value = bulletPoints.map(bulletText => ({
        words: bulletText.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
          text: w,
          visible: false
        }))
      }))
    } else if (!hasBulletPoints.value) {
      // Regular summary without bullet points
      if (props.summaryWords && props.summaryWords.length > 0) {
        summaryWords.value = props.summaryWords.map(w => ({ ...w, visible: false }))
      } else if (props.summary) {
        summaryWords.value = props.summary.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
          text: w,
          visible: false
        }))
      }
    }
    
    // Add keyboard event listeners when modal opens
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    
    // Play summary with printer effect
    await playSummaryWithPrinterEffect()
    
    // After summary finishes, play the two fixed questions
    await playFixedQuestions()
  } else {
    // Remove keyboard event listeners when modal closes
    window.removeEventListener('keydown', handleKeyDown)
    window.removeEventListener('keyup', handleKeyUp)
    
    // Stop any playing audio when modal closes
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.currentTime = 0
      if (currentAudio.src && currentAudio.src.startsWith('blob:')) {
        URL.revokeObjectURL(currentAudio.src)
      }
      currentAudio = null
    }
    // Reset all states when modal closes
    summaryAudioFinished.value = false
    showQuestion1.value = false
    showQuestion2.value = false
    question1AudioFinished.value = false
    question2AudioFinished.value = false
    isLoading.value = false
    isRecording.value = false
    openingSentenceWords.value = []
    bulletPointsWords.value = []
    defaultOpeningSentence.value = ''
    // Stop any active recording
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop()
    }
  }
})

// Watch for summaryWords prop changes - update local ref when props change
watch(() => props.summaryWords, (newWords) => {
  if (newWords && newWords.length > 0) {
    summaryWords.value = newWords.map(w => ({ ...w, visible: false }))
  }
}, { deep: true, immediate: true })

// Watch for summary prop changes - update local ref when props change
watch(() => props.summary, (newSummary) => {
  if (newSummary && (!props.summaryWords || props.summaryWords.length === 0)) {
    summaryWords.value = newSummary.split(/(\s+)/).filter(w => w.length > 0).map(w => ({
      text: w,
      visible: false
    }))
  }
}, { immediate: true })

// Clean up event listeners on component unmount
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 10000;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-container {
  background: #FFEC99;
  border: 8px solid white;
  border-radius: 40px;
  max-width: 600px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.3s ease;
  position: relative;
}

@keyframes slideUp {
  from {
    transform: translateY(50px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  border-bottom: 3px solid white;
}

.modal-title {
  font-family: 'Roboto', sans-serif;
  font-size: 2em;
  font-weight: 700;
  color: #008CBB;
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  font-size: 2.5em;
  color: #008CBB;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.close-button:hover {
  background: rgba(0, 140, 187, 0.1);
  transform: scale(1.1);
}

.modal-content {
  padding: 30px;
}

.summary-section {
  margin-bottom: 30px;
}

.summary-text {
  font-family: 'Roboto', sans-serif;
  font-size: 1.3em;
  line-height: 1.2;
  text-align: left;
  color: #FFFFFF;
  background: #008CBB;
  padding: 20px;
  border-radius: 20px;
  border: 3px solid #008CBB;
  min-height: 60px;
}

.summary-text :deep(.bold-highlight),
.summary-text .bold-highlight {
  font-weight: 700;
  color: #FFE600;
  background: rgba(255, 230, 0, 0.2);
  padding: 1px 0;
  font-family: 'Roboto', sans-serif;
  display: inline;
}

.summary-text :deep(.bold-highlight.bold-first),
.summary-text .bold-highlight.bold-first {
  border-top-left-radius: 3px;
  border-bottom-left-radius: 3px;
}

.summary-text :deep(.bold-highlight.bold-last),
.summary-text .bold-highlight.bold-last {
  border-top-right-radius: 3px;
  border-bottom-right-radius: 3px;
}

.summary-text :deep(.opening-sentence),
.summary-text .opening-sentence {
  margin-bottom: 16px;
  line-height: 1.2;
}

.summary-text :deep(.summary-bullet-list),
.summary-text .summary-bullet-list {
  list-style: none;
  padding: 0;
  margin: 0;
  margin-top: 8px;
}

.summary-text :deep(.summary-bullet-list li),
.summary-text .summary-bullet-list li {
  margin-bottom: 12px;
  padding-left: 0;
  line-height: 1.2;
}

.summary-text :deep(.summary-bullet-list li:last-child),
.summary-text .summary-bullet-list li:last-child {
  margin-bottom: 0;
}

.summary-text :deep(.summary-bullet-list li::before),
.summary-text .summary-bullet-list li::before {
  content: "• ";
  color: #FFE600;
  font-weight: 700;
  font-size: 1.2em;
  margin-right: 8px;
}

.word-visible {
  opacity: 1;
  transition: opacity 0.1s ease-in;
}

.word-hidden {
  opacity: 0;
}

.question-section {
  margin-bottom: 30px;
}

.question-text {
  font-family: 'Roboto', sans-serif;
  font-size: 1.4em;
  font-weight: 500;
  color: #008CBB;
  margin-bottom: 20px;
}

/* Likert Scale Styles */
.likert-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.likert-labels {
  display: flex;
  justify-content: space-between;
  font-family: 'Roboto', sans-serif;
  font-size: 1em;
  color: #666;
  margin-bottom: 10px;
}

.likert-label {
  flex: 1;
  text-align: center;
  transition: all 0.3s ease;
  padding: 8px 12px;
  border-radius: 8px;
  font-weight: 400;
  color: #666;
}

.likert-label.active {
  font-weight: 700;
  color: #008CBB;
  background: rgba(0, 140, 187, 0.1);
  transform: scale(1.05);
}

.likert-slider {
  width: 100%;
  height: 12px;
  border-radius: 10px;
  background: #e0e0e0;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
  margin: 20px 0;
}

.likert-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #686DF4;
  border: 4px solid #D4C5FA;
  cursor: pointer;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  transition: all 0.2s ease;
}

.likert-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
  background: #5a5fd8;
}

.likert-slider::-moz-range-thumb {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #686DF4;
  border: 4px solid #D4C5FA;
  cursor: pointer;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  transition: all 0.2s ease;
}

.likert-slider::-moz-range-thumb:hover {
  transform: scale(1.1);
  background: #5a5fd8;
}


/* Voice Input Styles */
.voice-input-container {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 20px;
}

.voice-input-button {
  font-family: 'Peachy Kink', 'Roboto', sans-serif;
  color: #FFE600;
  font-size: 1.5em;
  width: min(90%, 350px);
  height: 80px;
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

.voice-input-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 0 0 #3F4296;
}

.voice-input-button:active {
  transform: scale(0.95);
}

.voice-input-button.recording {
  background: linear-gradient(135deg, #ff6b9d 0%, #c44569 100%);
  border: 6px solid #ffbdcb;
  animation: pulse 1.5s infinite;
  box-shadow: 0 6px 0 0 #d73475;
}

.voice-input-button.loading {
  background: linear-gradient(135deg, #ffa726 0%, #ff7043 100%);
  border: 6px solid #fdc77b;
  box-shadow: 0 6px 0 0 #ffa323;
  cursor: not-allowed;
}

.voice-input-button:disabled {
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
  font-size: 1.3em;
  margin-right: 10px;
  display: block;
}

.recording-icon {
  animation: bounce 0.6s infinite alternate;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

.button-text {
  font-size: 1em;
  font-weight: bold;
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

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Scrollbar Styling */
.modal-container::-webkit-scrollbar {
  width: 8px;
}

.modal-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 10px;
}

.modal-container::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
}

.modal-container::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
}

/* Responsive Design */
@media (max-width: 768px) {
  .modal-container {
    width: 95%;
    max-height: 90vh;
    border-width: 4px;
    border-radius: 30px;
  }
  
  .modal-header {
    padding: 15px 20px;
  }
  
  .modal-title {
    font-size: 1.6em;
  }
  
  .close-button {
    font-size: 2em;
    width: 35px;
    height: 35px;
  }
  
  .modal-content {
    padding: 20px;
  }
  
  .summary-text {
    font-size: 1.1em;
    padding: 15px;
  }
  
  .question-text {
    font-size: 1.2em;
  }
  
  .likert-labels {
    font-size: 0.9em;
  }
  
  .voice-input-button {
    width: min(95%, 300px);
    height: 70px;
    font-size: 1.3em;
  }
}

@media (max-width: 480px) {
  .modal-container {
    width: 98%;
    border-width: 3px;
    border-radius: 25px;
  }
  
  .modal-title {
    font-size: 1.4em;
  }
  
  .summary-text {
    font-size: 1em;
    padding: 12px;
  }
  
  .question-text {
    font-size: 1.1em;
  }
  
  .likert-labels {
    font-size: 0.8em;
  }
  
  .voice-input-button {
    width: min(98%, 250px);
    height: 60px;
    font-size: 1.1em;
  }
}
</style>

