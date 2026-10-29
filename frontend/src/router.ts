import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import ImageSelection from './components/ImageSelection.vue'
import MapView from './views/MapView.vue'
import AreaView from './views/AreaView.vue'
import PhenomenonView from './views/PhenomenonView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
