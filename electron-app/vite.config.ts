import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
// @tailwindcss/vite 줄 삭제

export default defineConfig({
  plugins: [
    react(),
    // tailwindcss() 줄 삭제
  ],
})