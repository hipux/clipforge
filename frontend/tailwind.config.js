/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0f',
        surface: '#13131a',
        'surface-2': '#1c1c28',
        accent: '#06b6d4',
        'accent-hover': '#0891b2',
        success: '#10b981',
        danger: '#ef4444',
        warning: '#f59e0b',
      },
      boxShadow: {
        'glow': '0 0 20px rgba(6, 182, 212, 0.15)',
        'glow-lg': '0 0 40px rgba(6, 182, 212, 0.2)',
      },
    },
  },
  plugins: [],
}
