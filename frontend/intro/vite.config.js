import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Builds a single JS entry into FastAPI-served static assets.
// Output is referenced directly from `app/static/index.html`.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../../app/static/intro-build',
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: 'src/intro-entry.jsx',
      output: {
        entryFileNames: 'intro.bundle.js',
        assetFileNames: 'assets/[name][extname]'
      }
    }
  }
});

