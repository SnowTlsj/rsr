import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || 'localhost,127.0.0.1')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  const proxyTarget = (env.VITE_API_PROXY_TARGET || 'http://localhost:8100').trim();
  const hmrClientPortRaw = (env.VITE_HMR_CLIENT_PORT || '').trim();
  const hmrClientPort = Number(hmrClientPortRaw || '5174');

  return {
    plugins: [vue()],
    server: {
      host: true,
      port: 5173,
      strictPort: true,
      allowedHosts,
      hmr: Number.isFinite(hmrClientPort) && hmrClientPort > 0 ? { clientPort: hmrClientPort } : undefined,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/ws': {
          target: proxyTarget,
          ws: true,
          changeOrigin: true
        }
      }
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    }
  };
});
