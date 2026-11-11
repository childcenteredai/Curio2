import { createApp } from 'vue'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './style.css'
import './assets/theme.css'
import './assets/popup.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(router)
app.mount('#app')
