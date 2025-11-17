/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f7ff',
          100: '#e0efff',
          200: '#b8dcff',
          300: '#7cc0ff',
          400: '#36a1ff',
          500: '#0d84ff',
          600: '#0066d9',
          700: '#0052b0',
          800: '#003f87',
          900: '#002c5e',
        },
        wkms: {
          blue: '#1976d2',
          'blue-light': '#42a5f5',
          'blue-dark': '#0d47a1',
          'gray-light': '#f5f5f5',
          'gray-medium': '#e0e0e0',
          'gray-dark': '#424242',
        },
        background: {
          'gradient-start': '#e3f2fd',
          'gradient-end': '#f3e5f5',
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
      },
      boxShadow: {
        'chat': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
