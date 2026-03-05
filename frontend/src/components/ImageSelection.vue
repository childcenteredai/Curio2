<template>
  <div class="image-selection-wrapper">
    <div class="image-selection-container">
      <div class="selection-header">
        <h1 class="selection-title">Choose a Mystery Image!</h1>
      </div>
      
      <div class="images-grid">
        <div 
          v-for="(img, index) in images" 
          :key="index"
          class="image-card"
          @click="selectImage(img)"
          :class="{ selected: selectedImage === img.path }"
        >
          <div class="card-frame">
            <img 
              :src="img.path" 
              :alt="img.alt"
              class="preview-image"
            />
            <div class="overlay">
              <div class="overlay-content">
                <span class="icon">🔍</span>
                <!-- <span class="overlay-text">{{ img.name }}</span> -->
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="selection-footer">
        <button 
          @click="handleConfirm" 
          :disabled="!selectedImage"
          class="confirm-button"
        >
          <p class="confirm-button-text">Start</p>
        </button>
      </div>

      <div class="version-switch-wrapper">
        <label class="version-switch-label">Version</label>
        <button
          type="button"
          class="version-switch"
          :class="{ active: appVersion === 2 }"
          @click="toggleVersion"
        >
          <span class="version-option" :class="{ active: appVersion === 1 }">1</span>
          <span class="version-option" :class="{ active: appVersion === 2 }">2</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { CURIO_APP_VERSION, setCurioAppVersion, loadAppConfig } from '../constants/appConfig'

const router = useRouter()

const appVersion = ref<1 | 2>(1)

onMounted(async () => {
  await loadAppConfig()
  appVersion.value = CURIO_APP_VERSION.value
})

const toggleVersion = () => {
  const next = appVersion.value === 1 ? 2 : 1
  appVersion.value = next
  setCurioAppVersion(next)
}

interface ImageOption {
  path: string
  alt: string
  name: string
}

const images = ref<ImageOption[]>([
  {
    path: '/imgs/balloon.jpg',
    alt: 'Two girls with pink balloons',
    name: 'Balloon Mystery'
  },
  {
    path: '/imgs/bend.jpg',
    alt: 'Bending Water mystery',
    name: 'Bending Water Mystery'
  },
  {
    path: '/imgs/pepper.jpg',
    alt: 'Pepper mystery',
    name: 'Pepper Mystery'
  }
])

const selectedImage = ref<string>('')

const selectImage = (img: ImageOption) => {
  selectedImage.value = img.path
}

const handleConfirm = () => {
  if (selectedImage.value) {
    // Navigate to /chat with image path as query parameter
    router.push({
      path: '/chat',
      query: { image: selectedImage.value }
    })
  }
}
</script>


<style>
@font-face {
  font-family: 'Peachy Kink';
  src: url('../assets/fonts/peachy-keen-jf.otf') format('opentype');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
</style>

<style scoped>
.image-selection-wrapper {
  width: 100%;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  background: #F75C46;
}

.image-selection-container {
  width: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  padding-bottom: 80px;
  background: #F75C46;
  font-family: 'Comic Sans MS', cursive, sans-serif;
  box-sizing: border-box;
  position: relative;
}

.selection-header {
  text-align: center;
  margin-bottom: 20px;
  margin-top: 0;
  padding-top: 0;
}

.selection-title {
  font-family: 'Peachy Kink';
  font-size: clamp(2em, 8vw, 6em);
  color: #FAE100;
  border-color: #0011BB;
  -webkit-text-stroke: clamp(1px, 0.5vw, 4px) #0011BB;
  text-stroke: clamp(1px, 0.5vw, 4px) #0011BB;
  margin-bottom: 10px;
  text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
}

.selection-subtitle {
  font-size: 1.3em;
  color: rgba(255, 255, 255, 0.9);
  font-weight: bold;
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 40px;
  max-width: 80vw;
  width: 100%;
  margin-bottom: 60px;
}

.image-card {
  cursor: pointer;
  transition: transform 0.3s ease;
}

.image-card:hover {
  transform: translateY(-10px);
}

.image-card.selected {
  transform: translateY(-10px);
}

.card-frame {
  position: relative;
  border-radius: 30px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  border: 8px solid white;
  transition: all 0.3s ease;
  height: clamp(210px, 30vh, 310px);
}

.image-card.selected .card-frame {
  border-color: #ffe96b;
  box-shadow: 0 15px 40px rgba(255, 235, 107, 0.5);
}

.preview-image {
  width: 100%;
  height: clamp(250px, 28vh, 300px);
  object-fit: cover;
  transition: transform 0.3s ease;
}

.image-card:hover .preview-image {
  transform: scale(1.05);
}

.overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to bottom, rgba(255, 235, 107, 0.1), rgba(255, 235, 107, 0.7));
  display: flex;
  align-items: flex-end;
  padding: 20px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.image-card:hover .overlay,
.image-card.selected .overlay {
  opacity: 1;
}

.overlay-content {
  display: flex;
  align-items: center;
  gap: 10px;
  color: white;
  font-size: 1.1em;
  font-weight: bold;
}

.icon {
  font-size: 1.5em;
}

.selection-footer {
  display: flex;
  justify-content: center;
}

.confirm-button {
  background: #FFD000;
  color: #1266FF;
  border: none;
  padding: 0px 40px;
  border-radius: 100px;
  border-color: #FFF48C;
  border-width: 8px;
  border-style: solid;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 10px 0 0 #FF8C42;
  font-family: 'Comic Sans MS', cursive, sans-serif;
}

.confirm-button-text {
  font-family: 'Peachy Kink';
  font-size: 7em;
  font-weight: bold;
}
.confirm-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 10px 0 0 #FF8C42;
}

.confirm-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.version-switch-wrapper {
  position: absolute;
  bottom: 24px;
  right: 24px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-switch-label {
  font-size: 0.95em;
  color: rgba(255, 255, 255, 0.9);
  font-weight: bold;
}

.version-switch {
  display: flex;
  background: rgba(255, 255, 255, 0.3);
  border: 3px solid white;
  border-radius: 24px;
  padding: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.version-switch:hover {
  background: rgba(255, 255, 255, 0.5);
}

.version-switch .version-option {
  padding: 6px 16px;
  border-radius: 18px;
  font-weight: bold;
  font-size: 1em;
  color: rgba(255, 255, 255, 0.7);
  transition: all 0.2s ease;
}

.version-switch .version-option.active {
  background: #FFD000;
  color: #1266FF;
}

/* Responsive Design */
@media (max-width: 768px) {
  .selection-title {
    font-size: 2em;
  }
  
  .selection-subtitle {
    font-size: 1em;
  }
  
  .images-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  
  
  .confirm-button {
    padding: 15px 40px;
    font-size: 1.2em;
  }
}
</style>

