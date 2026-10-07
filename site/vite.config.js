import { defineConfig } from 'vite'

// base './' keeps every asset path relative, so dist/ works from any sub-folder
// (GitHub Pages, a USB stick served with `npx vite preview`, etc.).
export default defineConfig({
  base: './',
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
})
