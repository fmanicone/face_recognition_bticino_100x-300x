import { defineConfig } from 'vite'
import preact from '@preact/preset-vite'

export default defineConfig(({ command }) => ({
  plugins: [preact()],
  base: command === 'build' ? '/static/dist/' : '/',
  build: {
    outDir: '../backend/static/dist',
    emptyOutDir: true,
  },
}))
