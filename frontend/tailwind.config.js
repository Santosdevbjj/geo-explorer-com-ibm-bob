/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Paleta alinhada ao design system do IBM Bob / Sentinel
        'sentinel-bg': '#ffffff',
        'sentinel-surface': '#f7f8fa',
        'sentinel-border': '#e5e7eb',
        'sentinel-text': '#1f2328',
        'sentinel-muted': '#57606a',
        'sentinel-accent': '#3b82d4',
        'sentinel-purple': '#7c5cd8',
      },
    },
  },
  plugins: [],
}
