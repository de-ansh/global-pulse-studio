import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      // Navbar links to the backend's Swagger UI, which loads its schema from /openapi.json.
      '/docs': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/openapi.json': { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
