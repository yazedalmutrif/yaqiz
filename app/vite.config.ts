import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: http://localhost:5174 with /api (incl. WebSocket) and /voices proxied to the Yaqiz service.
// Build: dist/ is served by the Yaqiz service itself at http://127.0.0.1:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', ws: true, changeOrigin: true },
      '/voices': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 900 },
})
