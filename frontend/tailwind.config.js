/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Primary brand — USDT/emerald, used sparingly: actions, positives,
        // active states, progress. NOT a background wash for the whole UI.
        brand: {
          50: '#ecfdf3',
          100: '#d1fadf',
          200: '#a6f4c5',
          300: '#6ce9a6',
          400: '#32d583',
          500: '#12b76a',
          600: '#0e9f5f',
          700: '#0c7c4b',
          800: '#0a5f3b',
          900: '#07452c',
          950: '#032e1e',
        },
        // Accent — muted gold for VIP/reward touches only.
        accent: {
          50: '#1c1508',
          100: '#28201060', // unused in dark; kept for compat
          200: '#3c2f10',
          300: '#5c4a1a',
          400: '#8a6d1f',
          500: '#c99a2c',
          600: '#e3b341',
          700: '#f0c75e',
          800: '#f5d98c',
          900: '#faecc4',
        },
        // Dark surface scale — the backbone of the whole redesign. Every
        // component inherits by referencing these tokens, never hex values.
        surface: {
          50: '#141B24', // elevated (cards in dark: lowest usage)
          100: '#10161e', // slightly elevated input/track
          200: '#1b232e', // borders on cards
          300: '#2a3542', // strong borders / dividers
          400: '#46566b', // icons, faint text
          500: '#64748b', // secondary text
          600: '#8b9bb0', // body text muted-strong
          700: '#b6c2d1', // primary text on cards
          800: '#dde5ee', // bright text
          900: '#0B1016', // secondary background
          950: '#07090D', // primary background
        },
        // Status hues (dark-tuned).
        danger: {
          50: '#2a1215',
          100: '#3d1a1e',
          300: '#7f2d33',
          400: '#b3424a',
          500: '#e5484d',
          600: '#ec5d62',
          700: '#ff8589',
          900: '#ffd1d3',
        },
        info: {
          50: '#0f1c2e',
          100: '#15263c',
          300: '#1e4a70',
          400: '#2a6ea6',
          500: '#3b8fd4',
          600: '#5aa8e6',
          700: '#86c4f0',
          900: '#c9e8fb',
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
        // Depth via elevation + ring, not glow. Subtle borders do the work.
        card: '0 1px 2px rgb(0 0 0 / 0.4), 0 0 0 1px rgb(255 255 255 / 0.04)',
        'card-hover': '0 8px 24px rgb(0 0 0 / 0.45), 0 0 0 1px rgb(255 255 255 / 0.06)',
        glow: '0 0 0 1px rgb(18 183 106 / 0.35), 0 4px 24px rgb(18 183 106 / 0.12)',
        none: 'none',
      },
      borderColor: {
        DEFAULT: '#1b232e',
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
        'fade-in': 'fade-in 0.2s ease-out both',
        'fade-in-up': 'fade-in-up 0.3s ease-out both',
        'scale-in': 'scale-in 0.16s ease-out both',
      },
    },
  },
  plugins: [],
};
