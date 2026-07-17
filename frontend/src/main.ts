import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

// 主题在渲染前应用，避免闪烁；默认深色，auto 跟随系统
import { applyTheme } from './theme'
applyTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
