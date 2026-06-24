/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#f6f7f9',
        surface: '#ffffff',
        'surface-2': '#f1f3f6',
        accent: '#4f46e5',          // indigo-600
        'accent-hover': '#4338ca',  // indigo-700
        'accent-light': '#eef2ff',  // indigo-50
        'accent-fg': '#4f46e5',
        success: '#16a34a',
        danger: '#dc2626',
        warning: '#d97706',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)',
        'card': '0 1px 3px rgba(16,24,40,0.05), 0 4px 12px rgba(16,24,40,0.06)',
        'card-hover': '0 6px 20px rgba(16,24,40,0.10), 0 2px 6px rgba(16,24,40,0.06)',
        'btn': '0 1px 2px rgba(79,70,229,0.25)',
      },
      borderRadius: {
        'xl': '0.875rem',
        '2xl': '1.125rem',
      },
    },
  },
  plugins: [],
}
