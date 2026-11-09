import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import ImageSelection from './components/ImageSelection.vue'
import MapView from './views/MapView.vue'
import AreaView from './views/AreaView.vue'
import PhenomenonView from './views/PhenomenonView.vue'
import ExplanationView from './views/ExplanationView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Question-asking with AI version
    {
      path: '/',
      name: 'Map',
      component: MapView
    },
    {
      path: '/area/:area',
      name: 'Area',
      component: AreaView
    },
    {
      path: '/area/:area/:phenomenon',
      name: 'Phenomenon',
      component: PhenomenonView
    },
    // Direct instruction with AI version: same map and room selection, then Nova
    // explains the phenomenon instead of the question-asking chat
    {
      path: '/direct',
      name: 'DirectMap',
      component: MapView,
      meta: { version: 'direct' }
    },
    {
      path: '/direct/area/:area',
      name: 'DirectArea',
      component: AreaView,
      meta: { version: 'direct' }
    },
    {
      path: '/direct/area/:area/:phenomenon',
      name: 'DirectExplanation',
      component: ExplanationView,
      meta: { version: 'direct' }
    },
    // Teacher version: same as question-asking, but Nova's replies aren't spoken
    // and the teacher can edit the transcribed voice input before sending it
    {
      path: '/teacher',
      name: 'TeacherMap',
      component: MapView,
      meta: { version: 'teacher' }
    },
    {
      path: '/teacher/area/:area',
      name: 'TeacherArea',
      component: AreaView,
      meta: { version: 'teacher' }
    },
    {
      path: '/teacher/area/:area/:phenomenon',
      name: 'TeacherPhenomenon',
      component: PhenomenonView,
      meta: { version: 'teacher' }
    },
    // Previous three-picture flow, kept for now
    {
      path: '/legacy',
      name: 'ImageSelection',
      component: ImageSelection
    },
    {
      path: '/chat',
      name: 'Chat',
      component: Home
    }
  ]
})

export default router
