import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'

// 只測不需要畫面的邏輯（#71），不載入 vite.config.ts 的 Vue / Element Plus / HTML 外掛
export default defineConfig({
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/__tests__/*.test.ts'],
  },
})
