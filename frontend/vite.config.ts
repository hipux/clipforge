import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',  // Listen on all interfaces for VPN compatibility
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:8000',  // Use http://, Vite handles the upgrade
        ws: true,
      },
      '/files': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/downloads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
