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
    // 基础路径设置，用于 Nginx 反代理
    base: './',
    // 构建选项
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      rollupOptions: {
        output: {
          // 静态资源分目录存放
          assetFileNames: (assetInfo) => {
            if (assetInfo.name && assetInfo.name.endsWith('.css')) {
              return 'css/[name].[hash][extname]';
            }
            if (assetInfo.name && assetInfo.name.endsWith('.js')) {
              return 'js/[name].[hash][extname]';
            }
            return 'assets/[name].[hash][extname]';
          },
          chunkFileNames: 'js/[name].[hash].js',
          entryFileNames: 'js/[name].[hash].js',
        }
      }
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
