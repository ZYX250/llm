import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server:{
    host: true,
    port:5173,
    // 允许任意域名访问（ngrok / cpolar / cloudflared 换地址都不再 403）
    allowedHosts: true,
    proxy:{
      '/api':{
        target:'http://127.0.0.1:8000',
        changeOrigin:true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
