import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv, PluginOption } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const vite_host = new URL(env.VITE_API_BASE_URL).hostname

  // ** [修改] 动态加载插件 **
  const plugins: PluginOption[] = [vue()];
  if (mode !== 'production') {
    plugins.push(vueDevTools());
  }

  return {
    plugins, // 使用动态插件数组
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
    define: {
      // 确保全局类型定义被包含
      global: 'globalThis',
    },
    server: {
      allowedHosts: [vite_host],
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL,
          changeOrigin: true,
        },
        '/token': {
          target: env.VITE_API_BASE_URL,
          changeOrigin: true,
        },
        '/users': {
          target: env.VITE_API_BASE_URL,
          changeOrigin: true,
        }
      }
    }
  }
})
