/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        builders: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        discord: {
          50: '#f0f2ff',
          100: '#e6e9ff',
          200: '#d0d6ff',
          300: '#b0bbff',
          400: '#8a96ff',
          500: '#5865f2',
          600: '#4752c4',
          700: '#3c4aa0',
          800: '#343d7c',
          900: '#2e3558',
        },
        amazon: {
          50: '#fff8e1',
          100: '#ffecb3',
          200: '#ffe082',
          300: '#ffd54f',
          400: '#ffca28',
          500: '#ff9800',
          600: '#fb8c00',
          700: '#f57c00',
          800: '#ef6c00',
          900: '#e65100',
        }
      }
    },
  },
  plugins: [],
}