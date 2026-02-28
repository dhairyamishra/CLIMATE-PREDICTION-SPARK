import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2020',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-charts': ['recharts'],
          'vendor-map': ['maplibre-gl'],
          'vendor-ui': ['lucide-react', '@radix-ui/react-slider', '@radix-ui/react-select', '@radix-ui/react-dialog', '@radix-ui/react-popover', '@radix-ui/react-tooltip'],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})
