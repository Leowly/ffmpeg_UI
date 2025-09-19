// src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'

// --- Ant Design Vue 相关引入 ---
import Antd from 'ant-design-vue' // 引入 Ant Design Vue
import 'ant-design-vue/dist/reset.css'

const app = createApp(App)

app.use(createPinia())
app.use(Antd)

app.mount('#app')
