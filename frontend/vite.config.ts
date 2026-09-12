import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_');
  const target = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': { target, changeOrigin: false },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      maxWorkers: 1,
    },
  };
});
