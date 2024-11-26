/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/*",
    "./static/src/*",
    "./node_modules/flowbite/*"
  ],
  theme: {
    extend: {
      keyframes: {
        gradientHover: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
      },
      animation: {
        'gradient-hover': 'gradientHover 2s ease infinite',
      },
      backgroundImage: {
        'gradient-hover': 'linear-gradient(270deg, rgba(155, 89, 182, 1), rgba(255, 255, 255, 1))',
      },
      backgroundSize: {
        '200%': '200% 200%',
      },
    },
  },
  plugins: [
    require("flowbite/plugin"),
  ],
}