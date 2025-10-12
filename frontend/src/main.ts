// src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'

// --- Ant Design Vue 相关引入 ---
import Antd from 'ant-design-vue' // 引入 Ant Design Vue
import 'ant-design-vue/dist/reset.css'
import axios from 'axios'

// 配置 Axios 默认值
axios.defaults.withCredentials = true

// 在应用启动时检查 localStorage 中是否存在 token，并设置到 axios 默认头中
const token = localStorage.getItem('access_token');
if (token) {
  axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
}

const app = createApp(App)

app.use(createPinia())
app.use(Antd)

app.mount('#app')
