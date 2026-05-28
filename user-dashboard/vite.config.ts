import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
  build: {
    outDir: 'dist',
  },
  server: {
    port: 5174,
    proxy: {
      '/auth': 'https://extract.kafcenter.com',
      '/api': 'https://extract.kafcenter.com',
    }
  }
})
