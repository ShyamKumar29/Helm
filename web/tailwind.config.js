/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // "night bridge" — instrument panel at sea, lit only by its own readouts.
        page: '#0A0D10',
        panel: '#111720',
        'panel-light': '#F4F6F5',
        accent: {
          DEFAULT: '#2FE0B8', // sounder green — depth-sounder / radar phosphor, not startup mint
          dim: '#12332C',
        },
        danger: '#FF5C5C', // flare red
        warning: '#F0A93E', // brass caution
        info: '#4FB3D9', // chart-plotter cyan
        purple: '#A78BFA',
        text: {
          primary: '#ECF2EF', // chart paper
          secondary: '#8FA39D', // sea mist
          muted: '#56635F',
        },
        border: '#1C242B',
      },
      backgroundImage: {
        hero: 'linear-gradient(160deg, #0D2620 0%, #0A0D10 68%)',
      },
      borderRadius: {
        card: '16px',
        pill: '999px',
      },
      fontFamily: {
        display: ['"Geist Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', '"JetBrains Mono"', 'monospace'],
        serif: ['"Fraunces"', 'ui-serif', 'Georgia', 'serif'],
      },
      transitionDuration: {
        DEFAULT: '200ms',
      },
    },
  },
  plugins: [],
}
