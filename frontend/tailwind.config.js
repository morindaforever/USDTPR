/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Primary brand — deep teal/green tuned for a fintech/crypto feel.
        brand: {
          50: '#eefbf4',
          100: '#d6f5e4',
          200: '#b0eacf',
          300: '#7bd8b3',
          400: '#46c096',
          500: '#23a67d',
          600: '#158565',
          700: '#126b53',
          800: '#115544',
          900: '#0f4639',
          950: '#04281f',
        },
        // Accent — gold/amber for VIP and rewards touches.
        accent: {
          50: '#fffaeb',
          100: '#fef0c7',
          200: '#fedf89',
          300: '#fec84b',
          400: '#fdb022',
          500: '#f79009',
          600: '#dc6803',
          700: '#b54708',
          800: '#93370d',
          900: '#7a2e0e',
        },
        // Dark surfaces for the dashboard shell.
        surface: {
          50: '#f6f8fa',
          100: '#eceff3',
          200: '#d5dbe2',
          300: '#b1bdc8',
          400: '#8796a5',
          500: '#68798c',
          600: '#536273',
          700: '#45505e',
          800: '#3c4550',
          900: '#0d1520',
          950: '#080e15',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        display: ['Sora', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(13 21 32 / 0.05), 0 1px 3px 0 rgb(13 21 32 / 0.08)',
        'card-hover': '0 4px 6px -1px rgb(13 21 32 / 0.08), 0 10px 24px -4px rgb(13 21 32 / 0.12)',
        glow: '0 0 0 1px rgb(35 166 125 / 0.25), 0 4px 24px rgb(35 166 125 / 0.25)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out both',
        'fade-in-up': 'fade-in-up 0.35s ease-out both',
        'scale-in': 'scale-in 0.18s ease-out both',
      },
    },
  },
  plugins: [],
};
