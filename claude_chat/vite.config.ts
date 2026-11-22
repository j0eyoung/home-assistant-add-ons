import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  root: 'web',
  // Relative asset paths so the app works behind Home Assistant ingress.
  base: './',
  plugins: [react()],
  build: { outDir: '../dist', emptyOutDir: true, chunkSizeWarningLimit: 1500 },
  server: { proxy: { '/api': 'http://127.0.0.1:8099', '/ws': { target: 'ws://127.0.0.1:8099', ws: true } } },
})
