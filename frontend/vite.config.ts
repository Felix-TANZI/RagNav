// frontend/vite.config.ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En développement, /api est relayé vers GANDAL-AI (backend FastAPI, port 8090)
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8090',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
