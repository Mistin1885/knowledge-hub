/** @type {import('tailwindcss').Config} */

// Every themed color reads from a CSS variable (see index.css) so the whole
// app switches with the `dark` class on <html> — components keep using the
// same utility names (neutral-*, indigo-*, …) in both themes.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

const scale = (family, shades) =>
  Object.fromEntries(shades.map((s) => [s, v(`${family}-${s}`)]));

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: v('surface'),
        canvas: v('canvas'),
        primary: { DEFAULT: v('primary'), hover: v('primary-hover'), muted: v('primary-muted') },
        danger: { DEFAULT: v('danger'), hover: v('danger-hover'), muted: v('danger-muted') },
        neutral: scale('neutral', [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        indigo: scale('indigo', [50, 100, 200, 300, 400, 500, 600, 700, 900]),
        amber: scale('amber', [50, 200, 300, 400, 600, 700, 800, 900]),
        red: scale('red', [50, 200, 300, 500, 600, 700]),
        emerald: scale('emerald', [50, 400, 500, 600, 700]),
      },
    },
  },
  plugins: [],
};
