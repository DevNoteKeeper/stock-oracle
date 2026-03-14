// tailwind.config.js
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}", // ← 이게 없으면 클래스 전부 제거됨
    "./electron/**/*.{js,cjs}",
  ],
  theme: { extend: {} },
  plugins: [],
};
