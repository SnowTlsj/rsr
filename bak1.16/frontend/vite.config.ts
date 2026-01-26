import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,            // 允许 0.0.0.0 监听（容器里需要）
    port: 5173,
    strictPort: true,
    allowedHosts: ['nas.tlsi.top', '127.0.0.1', 'localhost'],
    hmr: { clientPort: 5174 } // 宿主机访问端口（docker 映射 5174:5173）
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  }
})
