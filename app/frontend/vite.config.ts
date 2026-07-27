import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(() => {
  // Read from process.env (Node context at config-eval time), not import.meta.env
  // (client-bundled code only). docker-compose sets this to the backend's
  // service-name DNS (http://be:8000) for the containerized frontend; outside
  // Docker it's unset, falling back to a backend run directly on the host.
  const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        // Frontend calls VITE_API_BASE_URL='/api' + a relative path (e.g. 'auth/login'),
        // but app/backend serves everything under /api/v1 (settings.api_v1_prefix) —
        // rewrite here so the two conventions line up without changing either one.
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, '/api/v1'),
        },
      },
    },
  }
})
