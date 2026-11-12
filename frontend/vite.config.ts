import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Backend has no CORS middleware — the dev proxy keeps requests same-origin.
      '/positions': 'http://localhost:8000',
      '/portfolio': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/market-pulse': 'http://localhost:8000',
      '/sentiment': 'http://localhost:8000',
      '/glossary': 'http://localhost:8000',
      '/predictions': 'http://localhost:8000',
      '/risk-profile': 'http://localhost:8000',
      '/themes': 'http://localhost:8000',
    },
  },
})
