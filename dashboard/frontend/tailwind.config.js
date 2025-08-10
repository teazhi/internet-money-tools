/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontSize: {
        // Override default font sizes to be larger
        'xs': ['0.8rem', { lineHeight: '1rem' }],     // was 0.75rem
        'sm': ['0.9rem', { lineHeight: '1.25rem' }],  // was 0.875rem  
        'base': ['1.1rem', { lineHeight: '1.5rem' }], // was 1rem
        'lg': ['1.2rem', { lineHeight: '1.75rem' }],  // was 1.125rem
        'xl': ['1.35rem', { lineHeight: '1.75rem' }], // was 1.25rem
        '2xl': ['1.6rem', { lineHeight: '2rem' }],    // was 1.5rem
        '3xl': ['2rem', { lineHeight: '2.25rem' }],   // was 1.875rem
      },
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