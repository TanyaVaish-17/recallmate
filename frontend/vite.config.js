import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// envDir '..' lets Vite read VITE_API_URL from the .env in the repo root.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
})
