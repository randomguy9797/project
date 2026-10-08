import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ command }) => ({
  // In production FastAPI exposes this directory at /static/dist/. Keep the
  // development base at / so `npm run dev` continues to use Vite normally.
  base: command === 'build' ? '/static/dist/' : '/',
  plugins: [vue()],
  server: {
    proxy: {
      // Forward all /api requests to FastAPI during development
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Forward legacy HTML routes so the dev server doesn't 404 on them
      '/login': { target: 'http://localhost:8000', changeOrigin: true },
      '/logout': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    // Output directly into FastAPI's static directory so it is served at /static/dist/
    outDir: '../app/static/dist',
    emptyOutDir: true,
  },
}))
