/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 950: '#070d1f', 900: '#0c1530', 800: '#121f45', 700: '#1a2c5c' },
        storm: { 50: '#eef4ff', 100: '#dbe7ff', 200: '#bcd2ff', 400: '#5b92f5', 500: '#3b78ee', 600: '#2a5fd8', 700: '#2149ad' },
        volt: { 400: '#ffc24a', 500: '#fb9d1c', 600: '#e8820c' },
        aqua: { 400: '#35d6e6', 500: '#14b8cc' },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Outfit', 'Plus Jakarta Sans', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 1px 2px rgba(15,23,42,.04), 0 8px 24px -8px rgba(33,73,173,.14)',
        lift: '0 2px 4px rgba(15,23,42,.05), 0 16px 32px -10px rgba(33,73,173,.28)',
        glow: '0 8px 30px -6px rgba(251,157,28,.55)',
      },
      keyframes: {
        rain: { '0%': { transform: 'translateY(-20vh)', opacity: 0 }, '10%': { opacity: 0.7 }, '100%': { transform: 'translateY(110vh)', opacity: 0 } },
        drift: { '0%,100%': { transform: 'translateX(0)' }, '50%': { transform: 'translateX(40px)' } },
        flash: { '0%,92%,100%': { opacity: 0 }, '94%': { opacity: 0.55 }, '96%': { opacity: 0.1 }, '98%': { opacity: 0.45 } },
        rise: { '0%': { opacity: 0, transform: 'translateY(14px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
      },
      animation: {
        rain: 'rain 1.4s linear infinite',
        drift: 'drift 14s ease-in-out infinite',
        flash: 'flash 7s ease-in-out infinite',
        rise: 'rise .5s ease-out both',
      },
    },
  },
  plugins: [],
}
