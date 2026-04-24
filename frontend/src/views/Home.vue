<template>
  <div class="home-container">
    <div class="home-bg-decorations" aria-hidden="true">
      <img
        class="home-bg-decor home-bg-green-blur3"
        src="/imgs/green_blur3.svg"
        alt=""
      />
      <img
        class="home-bg-decor home-bg-green-circle"
        src="/imgs/green_circle.svg"
        alt=""
      />
      <img
        class="home-bg-decor home-bg-orange-blur3"
        src="/imgs/orange_blur3.svg"
        alt=""
      />
    </div>
    <!-- Left side - Image display -->
    <div class="image-section">
      <div class="image-and-bubbles">
        <div class="image-container">
          <!-- Framed like chat panel: outer blue border, white mat, inner subtle rim -->
          <div class="picture-card">
            <div class="picture-card-mat">
              <div class="picture-card-inner">
                <div class="picture-card-clip">
                  <img 
                    :src="currentImage" 
                    :alt="imageAlt"
                    class="main-image"
                    @error="handleImageError"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="image-toolbar">
        <button type="button" @click="handleSwitchImage" class="switch-image-button">
          <i class="fa-solid fa-arrow-left switch-image-button-icon" aria-hidden="true" />
          <span class="switch-image-button-text">Back</span>
        </button>
        <button
          type="button"
          @click="handleNewChat"
          class="new-chat-button"
          :disabled="conversationRef?.isLoading || false"
          title="Start new chat"
        >
          <i class="fa-solid fa-arrows-rotate new-chat-icon" aria-hidden="true" />
        </button>
      </div>
    </div>

    <!-- Right side - Chat interface -->
    <div class="chat-section">
      <Conversation
        ref="conversationRef"
        :selectedImagePath="currentImage"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Conversation from '../components/Conversation.vue'

const route = useRoute()
const router = useRouter()

const currentImage = ref('/imgs/balloon.jpg')
const imageAlt = ref('Two girls with pink balloons - friendly cartoon illustration')
const conversationRef = ref<InstanceType<typeof Conversation> | null>(null)

const handleImageError = () => {
  console.log('Image failed to load, using fallback')
  // Could set a fallback image here
}

const handleSwitchImage = () => {
  // Navigate back to image selection
  router.push('/')
}

const handleNewChat = async () => {
  if (conversationRef.value) {
    if (conversationRef.value.isLoading) return
    await conversationRef.value.startNewChat()
  }
}

// Get image from route query parameter
onMounted(() => {
  const imagePath = route.query.image as string
  if (imagePath) {
    currentImage.value = imagePath
    
    // Update alt text based on selected image
    if (imagePath.includes('balloon.jpg')) {
      imageAlt.value = 'Two girls with pink balloons - friendly cartoon illustration'
    } else if (imagePath.includes('bend.jpg')) {
      imageAlt.value = 'Bending light mystery - scientific exploration'
    } else if (imagePath.includes('salt.jpg')) {
      imageAlt.value = 'Salt mystery - scientific exploration'
    }
  } else {
    // If no image is selected, redirect back to home
    router.push('/')
  }
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Kodchasan:wght@500;600;700&display=swap');

/* Align with Conversation.vue chat card */
.home-container {
  --border-blue: #BFE4F0;
  /* Image frame — stacked shadows (match chat buttons) */
  --shadow-layered: 0 8px 10px -6px rgba(0, 0, 0, 0.1), 0 20px 25px -5px rgba(0, 0, 0, 0.1);

  display: flex;
  align-items: flex-start;
  height: 100vh;
  width: 100vw;
  font-family: 'Kodchasan', system-ui, sans-serif;
  background: #ffffff;
  padding: 20px 0 20px 0;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  box-sizing: border-box;
}

.home-bg-decorations {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.home-bg-decor {
  position: absolute;
  display: block;
  max-width: none;
  height: auto;
  user-select: none;
}

/* 左上 — green_blur3 */
.home-bg-green-blur3 {
  left: -3%;
  top: 0;
  width: min(46vw, 340px);
  transform: translateY(-4%);
}

/* 底部中间 — green_circle */
.home-bg-green-circle {
  left: 50%;
  bottom: 2%;
  width: min(32vw, 220px);
  transform: translateX(-50%);
}

/* 右侧中间 — orange_blur3 */
.home-bg-orange-blur3 {
  right: -6%;
  top: 50%;
  width: min(52vw, 400px);
  transform: translateY(-50%);
  opacity: 0.95;
}

/* Image Section — slightly wider column so the picture reads larger */
.image-section {
  flex: 1.5;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  padding: 24px 16px 24px 32px;
  background: transparent;
  gap: 34px;
  min-height: 0;
  position: relative;
  z-index: 1;
}

.image-and-bubbles {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  min-height: 0;
  width: 100%;
  padding: 0 0 8px;
}

.image-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  width: 100%;
  max-width: min(960px, 100%);
}

/* Same shell as .chat-container: white card, cyan border, soft radius + shadow */
.picture-card {
  width: 100%;
  background: #ffffff;
  border: 6px solid var(--border-blue);
  border-radius: 24px;
  box-shadow: var(--shadow-layered);
  box-sizing: border-box;
}

.picture-card-mat {
  padding: clamp(28px, 4vw, 36px);
  background: #ffffff;
  border-radius: 22px;
}

/* inset box-shadow + overflow:hidden on same node clips the shadow in browsers */
.picture-card-inner {
  position: relative;
  border-radius: 18px;
  border: 1px solid rgba(61, 87, 106, 0.14);
  background: #ffffff;
}

.picture-card-clip {
  overflow: hidden;
  border-radius: 17px;
}

.picture-card-inner::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: inset 0 4.15px 4.15px 0 rgba(0, 0, 0, 0.25);
  pointer-events: none;
  z-index: 1;
}

.image-toolbar {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  flex-shrink: 0;
  gap: 12px;
}

.switch-image-button {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: #ffffff;
  color: #486174;
  border: 2px solid var(--border-blue);
  padding: 10px 22px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 1em;
  font-weight: 600;
  transition: transform 0.2s ease, filter 0.2s ease, border-color 0.2s ease;
  white-space: nowrap;
  box-shadow: var(--shadow-layered);
  z-index: 10;
}

.switch-image-button-icon {
  font-size: 1.05rem;
  line-height: 1;
}

.switch-image-button-text {
  font-family: 'Inter', sans-serif;
  font-size: 1.05rem;
  font-weight: 600;
  color: #486174;
}

.switch-image-button:hover {
  filter: brightness(1.05);
  transform: scale(1.02);
  border-color: #568E9C;
}

.switch-image-button:active {
  transform: scale(0.98);
}

.main-image {
  display: block;
  width: 100%;
  height: auto;
  max-height: min(88vh, 940px);
  object-fit: contain;
  transition: transform 0.3s ease;
}

.main-image:hover {
  transform: scale(1.01);
}

.chat-section {
  flex: 1;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px 24px 24px 16px;
  background: transparent;
  overflow: visible;
  position: relative;
  z-index: 1;
}

/* Icon-only pill — aligned with Back, paired on the right of the toolbar */
.new-chat-button {
  margin: 0;
  flex-shrink: 0;
  padding: 10px 14px;
  border-radius: 999px;
  background: #ffffff;
  color: #486174;
  border: 2px solid var(--border-blue);
  cursor: pointer;
  transition: transform 0.2s ease, filter 0.2s ease, border-color 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-layered);
}

.new-chat-button:hover:not(:disabled) {
  filter: brightness(1.05);
  transform: scale(1.02);
  border-color: #568E9C;
}

.new-chat-button:active:not(:disabled) {
  transform: scale(0.98);
}

.new-chat-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

.new-chat-icon {
  font-size: 1.375rem;
  line-height: 1;
}

/* Responsive Design */
@media (max-width: 768px) {
  .home-container {
    flex-direction: column;
  }
  
  .image-section {
    flex: 0 0 auto;
    max-height: 48vh;
    padding: 16px 12px 12px;
  }

  .image-and-bubbles {
    padding: 0;
    justify-content: flex-start;
  }
  
  .switch-image-button {
    padding: 8px 16px;
    font-size: 0.9em;
  }
  
  .chat-section {
    flex: 1;
    padding: 16px 12px 12px;
    min-height: 0;
    align-items: flex-start;
  }
  
  .main-image {
    max-height: min(40vh, 420px);
  }

  .picture-card-mat {
    padding: 12px;
  }

  .image-toolbar {
    gap: 8px;
  }

  .new-chat-button {
    padding: 8px 12px;
  }

  .new-chat-icon {
    font-size: 1.25rem;
  }

  .home-bg-green-blur3 {
    width: min(58vw, 260px);
    left: -6%;
  }

  .home-bg-green-circle {
    width: min(40vw, 160px);
    bottom: 1%;
  }

  .home-bg-orange-blur3 {
    width: min(70vw, 300px);
    right: -12%;
  }
}
</style>
