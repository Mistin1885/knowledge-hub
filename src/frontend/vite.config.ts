import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backend = process.env.VITE_BACKEND ?? 'localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: `http://${backend}`,
        changeOrigin: true,
      },
      '/collab': {
        target: `ws://${backend}`,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query'],
          editor: [
            '@tiptap/react',
            '@tiptap/starter-kit',
            '@tiptap/extension-collaboration',
            '@tiptap/extension-collaboration-cursor',
            'yjs',
            'y-websocket',
          ],
          d3: ['d3-force', 'd3-zoom', 'd3-drag', 'd3-selection'],
        },
      },
    },
  },
});
