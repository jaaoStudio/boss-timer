import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import type { ConfigEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import VitePluginHtmlEnv from 'vite-plugin-html-env'
import fs from 'fs'

// https://vitejs.dev/config/
export default defineConfig((config: ConfigEnv) => {
  // Vite 默認情況下不加載 .env 文件，使用導出的 loadEnv 來加載
  const loadedEnv = loadEnv(config.mode, process.cwd(), '')
  return {
    base: loadedEnv.VITE_BASE_PUBLIC_PATH,
    plugins: [
      vue(),
      VitePluginHtmlEnv(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        '/images': fileURLToPath(new URL('./src/assets/images', import.meta.url)),
        '/icons': fileURLToPath(new URL('./src/assets/icons', import.meta.url)),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: '',
        },
      },
    },
    server: {
      https: {
        key: fs.readFileSync('./vite-key.pem'),
        cert: fs.readFileSync('./vite.pem'),
      },
      host: '0.0.0.0',
      port: 2255,
      proxy: {
        '/api': {
          target: 'https://10.5.71.159:1254',
          rewrite: (path) => path.replace(/^\/api/, ""),
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})