<template>
  <div class="image-selection-wrapper">
    <div class="image-selection-container">
      <!-- Background decorations: positioned vs. container, not vs. cards -->
      <div class="bg-decorations" aria-hidden="true">
        <img class="bg-decor bg-green-blur2" src="/imgs/green_blur2.svg" alt="" />
        <img class="bg-decor bg-purple-circle" src="/imgs/purple_circle.svg" alt="" />
        <img class="bg-decor bg-orange-blur2" src="/imgs/orange_blur2.svg" alt="" />
        <img class="bg-decor bg-colorful-dots" src="/imgs/colorful_dots.svg" alt="" />
        <img class="bg-decor bg-pink-blur" src="/imgs/pink_blur.svg" alt="" />
        <img class="bg-decor bg-green-blur1" src="/imgs/green_blur1.svg" alt="" />
        <img class="bg-decor bg-orange-blur" src="/imgs/orange_blur.svg" alt="" />
        <img class="bg-decor bg-plant1" src="/imgs/plant1.svg" alt="" />
        <img class="bg-decor bg-plant2" src="/imgs/plant2.svg" alt="" />
      </div>

      <div class="selection-header">
        <h1 class="selection-title">Choose a Mystery Image!</h1>
        <h2 class="selection-subtitle">Step into a world of curiosity and surprise</h2>
      </div>
      
      <div class="images-grid">
        <div 
          v-for="(img, index) in images" 
          :key="index"
          class="image-card"
          @click="goToChat(img)"
        >
          <div class="card-frame">
            <img
              :src="pasteTapeSrc[index % pasteTapeSrc.length]"
              class="frame-paste"
              alt=""
              aria-hidden="true"
            />
            <div class="card-frame-inner">
              <img
                :src="img.path"
                :alt="img.alt"
                class="preview-image"
              />
              <div class="overlay">
                <div class="overlay-content">
                  <!-- <span class="overlay-text">{{ img.name }}</span> -->
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="selection-footer">
        <div class="start-paste-wrap">
          <img
            class="start-paste-img"
            src="/imgs/start_paste.png"
            alt=""
            aria-hidden="true"
          />
          <div class="start-hint-overlay">
            <div class="start-hint-row">
              <p class="start-hint-text">
                Click on any image to <span class="start-hint-em">START</span> exploring
              </p>
              <img
                class="start-hint-glass"
                src="/imgs/glass.svg"
                alt=""
                aria-hidden="true"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { setCurioAppVersion, loadAppConfig } from '../constants/appConfig'

const router = useRouter()

onMounted(async () => {
  await loadAppConfig()
  setCurioAppVersion(1)
})

interface ImageOption {
  path: string
  alt: string
  name: string
}

/** Decorative tape per card (cycle if more than three images). */
const pasteTapeSrc = ['/imgs/paste1.svg', '/imgs/paste2.svg', '/imgs/paste3.svg'] as const

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

const goToChat = (img: ImageOption) => {
  router.push({
    path: '/chat',
    query: { image: img.path }
  })
}
</script>


<style>
@font-face {
  font-family: 'Krona One';
  src: url('../assets/fonts/KronaOne-Regular.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
</style>

<style scoped>
.image-selection-wrapper {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
  box-sizing: border-box;
  background: #ffffff;
}

.image-selection-container {
  width: 100%;
  height: 100%;
  max-height: 100%;
  box-sizing: border-box;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  justify-items: center;
  align-content: stretch;
  padding: clamp(36px, 20vh, 64px) clamp(8px, 1.5vw, 20px) clamp(40px, 24vh, 72px);
  background: #ffffff;
  font-family: 'Comic Sans MS', cursive, sans-serif;
  position: relative;
  isolation: isolate;
}

.bg-decorations {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: visible;
}

.bg-decor {
  position: absolute;
  display: block;
  max-width: none;
  height: auto;
  user-select: none;
}

/* 4–5: left upper — green_blur2 with purple_circle stacked on top */
.bg-green-blur2 {
  left: -4%;
  top: 6%;
  width: min(42vw, 280px);
  transform: translateY(-10%);
  z-index: 0;
}

.bg-purple-circle {
  left: clamp(-24px, -2vw, 0px);
  top: 8%;
  width: min(25vw, 100px);
  transform: translate(-6%, -8%);
  z-index: 1;
}

/* 9: center of the full view (container) */
.bg-orange-blur2 {
  right: -16%;
  top: 50%;
  width: min(55vw, 420px);
  transform: translate(-50%, -48%);
  z-index: 0;
  opacity: 0.95;
}

/* 7–6: colorful_dots left of pink_blur; first-card top area as % of container */
.bg-colorful-dots {
  left: 6%;
  top: 20%;
  width: min(18vw, 120px);
  transform: translate(0, -20%);
  z-index: 0;
}

.bg-pink-blur {
  left: 12%;
  top: 24%;
  width: min(32vw, 220px);
  transform: translate(-15%, -25%);
  z-index: 0;
}

/* 3: first image zone — bottom-left of typical first column (container %) */
.bg-green-blur1 {
  left: 10%;
  bottom: 20%;
  width: min(36vw, 260px);
  transform: translate(-8%, 18%);
  z-index: 0;
}

/* 8: title area — right side of header band */
.bg-orange-blur {
  right: -2%;
  top: 4%;
  width: min(28vw, 200px);
  transform: translate(5%, -5%);
  z-index: 0;
}

/* 1–2: bottom corners */
.bg-plant1 {
  left: 4%;
  bottom: -4%;
  width: min(32vw, 180px);
  max-height: 45vh;
  object-fit: contain;
  object-position: bottom left;
  z-index: 0;
}

.bg-plant2 {
  right: 4%;
  bottom: 10%;
  width: min(30vw, 180px);
  max-height: 45vh;
  object-fit: contain;
  object-position: bottom right;
  z-index: 0;
}

.selection-header {
  position: relative;
  z-index: 1;
  text-align: center;
  margin: 0 0 clamp(4px, 0.8vh, 10px);
  padding: 0;
  flex-shrink: 0;
}

.selection-title {
  font-family: 'Krona One';
  font-size: clamp(0.85rem, 3.2vw, 2rem);
  color: #2C4A3E;
  margin: 0 0 clamp(2px, 0.4vh, 6px);
  line-height: 1.15;
}

.selection-subtitle {
  font-family: 'Krona One';
  font-size: clamp(0.75rem, 1.8vw, 1.1rem);
  color: #6B7C7A;
  margin: 0;
  line-height: 1.2;
}

.images-grid {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: min(90vw, 1600px);
  height: 100%;
  max-height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(32px, 4vw, 40px);
  align-content: center;
  align-items: stretch;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.image-card {
  cursor: pointer;
  transition: transform 0.3s ease;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-card:hover {
  transform: translateY(-10px);
}

.images-grid .image-card:nth-child(1):hover .card-frame {
  border-color: #d093c4;
}

.images-grid .image-card:nth-child(2):hover .card-frame {
  border-color: #eeb1a6;
}

.images-grid .image-card:nth-child(3):hover .card-frame {
  border-color: #f0c174;
}

.card-frame {
  position: relative;
  border-radius: clamp(18px, 2.5vw, 30px);
  box-sizing: border-box;
  border: 3px solid #2c4a3e;
  padding: clamp(12px, 2vh, 22px);
  background: #fff;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  transition: all 0.3s ease;
  width: 100%;
  max-width: 100%;
  height: min(100%, clamp(280px, 36vh, 420px));
  max-height: min(100%, clamp(280px, 36vh, 420px));
}

.frame-paste {
  position: absolute;
  top: 0;
  left: 50%;
  z-index: 3;
  width: min(42%, 140px);
  height: auto;
  transform: translate(-50%, -42%);
  pointer-events: none;
}

.card-frame-inner {
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: 3px;
  overflow: hidden;
  background: #fff;
  box-shadow: inset 0 4px 4px 0 rgba(0, 0, 0, 0.25);
}

.preview-image {
  width: 100%;
  height: 100%;
  min-height: 0;
  object-fit: cover;
  display: block;
  border-radius: 0;
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
  background: linear-gradient(to bottom, rgba(255, 235, 107, 0.1), rgba(255, 235, 107, 0.4));
  display: flex;
  align-items: flex-end;
  padding: 20px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.image-card:hover .overlay {
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
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  width: 100%;
  max-height: clamp(52px, 11vh, 100px);
  pointer-events: none;
  flex-shrink: 0;
  align-items: flex-end;
}

/* Stack paste art + copy in one grid cell so overlay always matches image height */
.start-paste-wrap {
  position: relative;
  display: grid;
  width: min(96vw, 720px);
  max-width: 100%;
  max-height: clamp(52px, 11vh, 100px);
}

.start-paste-img {
  grid-row: 1;
  grid-column: 1;
  display: block;
  width: 100%;
  height: auto;
  max-height: clamp(52px, 11vh, 100px);
  object-fit: contain;
  object-position: center bottom;
  vertical-align: top;
  user-select: none;
}

.start-hint-overlay {
  grid-row: 1;
  grid-column: 1;
  z-index: 1;
  align-self: stretch;
  justify-self: stretch;
  width: 100%;
  min-height: 0;
  display: grid;
  place-content: center;
  place-items: center;
  padding: 0 10%;
  box-sizing: border-box;
  pointer-events: none;
}

.start-hint-row {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  gap: clamp(8px, 2vw, 20px);
  max-width: 100%;
}

.start-hint-glass {
  width: clamp(32px, 8vw, 64px);
  height: auto;
  flex-shrink: 0;
  object-fit: contain;
  user-select: none;
}

.start-hint-text {
  margin: 0;
  font-family: 'Krona One', sans-serif;
  font-size: clamp(0.52rem, 2.1vw, 1.15rem);
  line-height: 1.35;
  color: #2c4a3e;
  text-align: left;
  white-space: nowrap;
  flex-shrink: 0;
}

.start-hint-em {
  color: #E7815B;
  font-weight: 700;
  font-family: 'Krona One'
}

/* Responsive Design */
@media (max-width: 768px) {
  .image-selection-container {
    grid-template-rows: auto minmax(0, 1fr) auto;
    padding: clamp(12px, 2.5vh, 28px) clamp(8px, 2vw, 14px) clamp(12px, 2.5vh, 28px);
  }

  .selection-title {
    font-size: clamp(0.8rem, 4.2vw, 1.35rem);
  }

  .selection-subtitle {
    font-size: clamp(0.68rem, 3vw, 0.95rem);
  }

  .images-grid {
    grid-template-columns: 1fr;
    gap: clamp(8px, 2vh, 14px);
    align-content: center;
  }

  .card-frame {
    height: min(100%, clamp(120px, 22vh, 220px));
    max-height: min(100%, clamp(120px, 22vh, 220px));
  }

  .start-hint-text {
    font-size: clamp(0.45rem, 2.8vw, 0.8rem);
  }

  .start-paste-wrap {
    width: min(98vw, 720px);
    max-height: clamp(44px, 9vh, 88px);
  }

  .start-paste-img {
    max-height: clamp(44px, 9vh, 88px);
  }

  .selection-footer {
    max-height: clamp(44px, 9vh, 88px);
  }
}
</style>

