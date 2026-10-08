import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.js'
import { initCsrf } from './api/client.js'
import './assets/style.css'

initCsrf().then(() => {
  createApp(App).use(router).mount('#app')
})
