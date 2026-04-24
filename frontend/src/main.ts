import { createApp } from 'vue'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { loadAppConfig } from './constants/appConfig'

loadAppConfig()

const app = createApp(App)
app.use(router)
app.mount('#app')
