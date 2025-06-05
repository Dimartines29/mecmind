/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./mecmind_app/templates/**/*.html",
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        'royal-blue': '#4169E1',
        'dark-blue': '#0A1931',
        'royal-blue-light': '#6384e6',
        'dark-blue-light': '#162a48',
        'light-gray': '#D3D3D3',
        'background-light': '#f0f4ff',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
