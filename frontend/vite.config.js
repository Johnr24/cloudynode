import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/graph': {
        target: `http://${process.env.VITE_BACKEND_HOST || 'localhost:2155'}`,
        changeOrigin: true,
      },
      '/projects': {
        target: `http://${process.env.VITE_BACKEND_HOST || 'localhost:2155'}`,
        changeOrigin: true,
      },
      '/download': {
        target: `http://${process.env.VITE_BACKEND_HOST || 'localhost:2155'}`,
        changeOrigin: true,
      },
      '/scan-emails': {
        target: `http://${process.env.VITE_BACKEND_HOST || 'localhost:2155'}`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://${process.env.VITE_BACKEND_HOST || 'localhost:2155'}`,
        ws: true,
      },
    }
  }
})
