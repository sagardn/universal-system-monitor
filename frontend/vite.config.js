import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/ws': {
        target: 'ws://127.0.0.1:7777',
        ws: true,
      },
      '/api': {
        target: 'http://127.0.0.1:7777',
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
