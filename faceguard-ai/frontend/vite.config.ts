import path from 'node:path'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: false },
    resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
    server: {
      port: 5173,
      proxy: { '/api': { target: env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000', changeOrigin: true } },
    },
  }
})
