<template>
  <div class="home-container">
    <!-- Left side - Image display -->
    <div class="image-section">
      <button @click="handleSwitchImage" class="switch-image-button">
        <p class="switch-image-button-text">Choose Image</p>
      </button>
      <div class="image-container">
        <img 
          :src="currentImage" 
          :alt="imageAlt"
          class="main-image"
          @error="handleImageError"
        />
      </div>
    </div>

    <!-- Right side - Chat interface -->
    <div class="chat-section">
      <button 
        @click="handleNewChat"
        class="new-chat-button"
        :disabled="conversationRef?.isLoading || false"
      >
        <img :src="refreshIcon" alt="Refresh" class="new-chat-icon" />
      </button>
      <Conversation ref="conversationRef" :selectedImagePath="currentImage" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Conversation from '../components/Conversation.vue'
import refreshIcon from '../assets/imgs/refresh.png'

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
    // Use isLoading from the conversation component
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
.home-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  font-family: 'Comic Sans MS', cursive, sans-serif;
}

/* Image Section */
.image-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: #FFD000;
  position: relative;
}

.switch-image-button {
  position: absolute;
  top: 20px;
  left: 20px;
  background: #59A7F6;
  color: white;
  border: 6px solid #88E7FA;
  padding: 10px 20px;
  border-radius: 100px;
  cursor: pointer;
  font-size: 1em;
  font-weight: bold;
  transition: all 0.3s ease;
  white-space: nowrap;
  box-shadow: 0 6px 0 0 #008CBB;
  z-index: 10;
}

.switch-image-button-text {
  font-family: 'Peachy Kink';
  font-size: 2em;
  color: #FFE600;
}

.switch-image-button:hover {
  background: #59A7F6;
  transform: scale(1.05);
  box-shadow: 0 6px 0 0 #008CBB;
}

.switch-image-button:active {
  transform: scale(0.95);
}

.image-container {
  position: relative;
  max-width: 100%;
  max-height: 100%;
}

.main-image {
  width: 90%;
  height: auto;
  max-height: 80vh;
  object-fit: contain;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.5);
  transition: transform 0.3s ease;
}

.main-image:hover {
  transform: scale(1.02);
}

.chat-section {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: #F75C46;
  overflow: visible; /* Allow character image to overflow */
  position: relative;
}

.new-chat-button {
  position: absolute;
  top: 20px;
  right: 20px;
  font-family: 'Peachy Kink';
  color: #FFE600;
  font-size: 1.5em;
  padding: 10px 20px;
  border: none;
  border-radius: 50px;
  background: #59A7F6;
  border: 6px solid #88E7FA;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 6px 0 0 #008CBB;
  white-space: nowrap;
  z-index: 201;
}

.new-chat-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 0 0 #008CBB;
}

.new-chat-button:active:not(:disabled) {
  transform: scale(0.95);
}

.new-chat-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

.new-chat-icon {
  width: 1.8em;
  height: 1.8em;
  object-fit: contain;
}

.new-chat-text {
  font-weight: bold;
}

/* Responsive Design */
@media (max-width: 768px) {
  .home-container {
    flex-direction: column;
  }
  
  .image-section {
    flex: 0 0 40vh;
  }
  
  .switch-image-button {
    top: 10px;
    left: 10px;
    padding: 8px 16px;
    font-size: 0.9em;
  }
  
  .chat-section {
    flex: 1;
  }
  
  .main-image {
    max-height: 35vh;
  }
  
  .new-chat-button {
    top: 10px;
    right: 10px;
    font-size: 1.2em;
    padding: 8px 16px;
    border-width: 3px;
  }
  
  .new-chat-icon {
    font-size: 1em;
  }
  
  .new-chat-text {
    font-size: 0.9em;
  }
}
</style>
