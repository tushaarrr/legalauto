import type { Config } from "tailwindcss";

/*
  Colours map to the CSS custom properties in globals.css, so utilities like
  `bg-surface` theme themselves — there is no `dark:` variant anywhere in the
  components, and the two modes stay impossible to drift apart.
*/
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",

        "ink-primary": "var(--text-primary)",
        "ink-secondary": "var(--text-secondary)",
        "ink-muted": "var(--text-muted)",
        heading: "var(--heading)",

        brand: "var(--primary)",
        "brand-hover": "var(--primary-hover)",
        "on-brand": "var(--on-primary)",
        accent: "var(--accent)",

        good: "var(--good)",
        warn: "var(--warn)",
        crit: "var(--crit)",
        "good-bg": "var(--good-bg)",
        "warn-bg": "var(--warn-bg)",
        "crit-bg": "var(--crit-bg)",

        "chart-bar": "var(--chart-bar)",
        "chart-bar-2": "var(--chart-bar-2)",
        "chart-track": "var(--chart-track)",

        appbar: "var(--appbar)",
        rail: "var(--rail)",
        "rail-2": "var(--rail-2)",
        "rail-ink": "var(--rail-ink)",
        "rail-ink-active": "var(--rail-ink-active)",
      },
      fontFamily: {
        // One grotesque throughout, matching the product UI being mirrored:
        // headings are heavy weights of the same face, not a contrasting serif.
        display: ["var(--font-body)", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "var(--shadow-sm)",
        raised: "var(--shadow-md)",
      },
    },
  },
  plugins: [],
};

export default config;
