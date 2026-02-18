import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv, PluginOption } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '');

  // 防止意外情况，给个默认值
  const baseUrl = env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
  const vite_host = new URL(baseUrl).hostname

  const plugins: PluginOption[] = [vue()];
  if (mode !== 'production') {
    plugins.push(vueDevTools());
  }

  return {
    envDir: '..',

    plugins,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
    define: {
      global: 'globalThis',
    },
    base: './',
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      rollupOptions: {
        output: {
          assetFileNames: (assetInfo) => {
             // ... 保持原有代码 ...
             if (assetInfo.name && assetInfo.name.endsWith('.css')) return 'css/[name].[hash][extname]';
             if (assetInfo.name && assetInfo.name.endsWith('.js')) return 'js/[name].[hash][extname]';
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
          target: baseUrl,
          changeOrigin: true,
        },
        '/token': {
          target: baseUrl,
          changeOrigin: true,
        },
        '/users': {
          target: baseUrl,
          changeOrigin: true,
        },
        '/ws': {
          target: baseUrl,
          ws: true,
        }
      }
    }
  }
})
