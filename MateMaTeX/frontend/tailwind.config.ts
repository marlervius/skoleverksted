import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      /* -----------------------------------------------------------
         Colors — "Scholarly Craft" palette
         Maps to CSS variables for theme switching
         ----------------------------------------------------------- */
      colors: {
        bg: "hsl(var(--bg) / <alpha-value>)",
        surface: {
          DEFAULT: "hsl(var(--surface) / <alpha-value>)",
          elevated: "hsl(var(--surface-elevated) / <alpha-value>)",
        },
        border: "hsl(var(--border) / <alpha-value>)",
        "text-primary": "hsl(var(--text-primary) / <alpha-value>)",
        "text-secondary": "hsl(var(--text-secondary) / <alpha-value>)",
        "text-muted": "hsl(var(--text-muted) / <alpha-value>)",

        // Accent colors (from LaTeX tcolorbox palette)
        accent: {
          blue: "hsl(var(--accent-blue) / <alpha-value>)",
          green: "hsl(var(--accent-green) / <alpha-value>)",
          purple: "hsl(var(--accent-purple) / <alpha-value>)",
          orange: "hsl(var(--accent-orange) / <alpha-value>)",
          teal: "hsl(var(--accent-teal) / <alpha-value>)",
          red: "hsl(var(--accent-red) / <alpha-value>)",
          50: "#f1f6f6",
          100: "#dce9e8",
          200: "#bcd6d3",
          300: "#8fbab6",
          400: "#5e9893",
          500: "#3f7d78",
          600: "#2f6562",
          700: "#274f4d",
          800: "#223f3e",
          900: "#1d3534",
        },

        // Legacy compat (used by existing components)
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "hsl(var(--accent-blue) / <alpha-value>)",
          500: "hsl(var(--accent-blue) / <alpha-value>)",
          600: "hsl(210 70% 48% / <alpha-value>)",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },
        fjord: {
          50: "#f0f7ff", 100: "#e0effe", 200: "#bae0fd", 300: "#7cc8fc",
          400: "#36aaf8", 500: "#0c8ee9", 600: "#0070c7", 700: "#0159a1",
          800: "#064b85", 900: "#0b3f6e",
        },
        aurora: {
          50: "#f0fdf6", 100: "#dcfce9", 200: "#bbf7d4", 300: "#86efb3",
          400: "#4ade87", 500: "#22c563", 600: "#16a34d", 700: "#15803f",
          800: "#166535", 900: "#14532d",
        },
      },

      /* -----------------------------------------------------------
         Typography — Academic meets modern
         ----------------------------------------------------------- */
      fontFamily: {
        display: ['"Instrument Serif"', '"Playfair Display"', "Georgia", "serif"],
        sans: ['"DM Sans"', '"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },

      fontSize: {
        "xs": ["0.75rem", { lineHeight: "1rem" }],
        "sm": ["0.875rem", { lineHeight: "1.25rem" }],
        "base": ["1rem", { lineHeight: "1.5rem" }],
        "lg": ["1.125rem", { lineHeight: "1.75rem" }],
        "xl": ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem", { lineHeight: "2rem" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem" }],
        "4xl": ["2.25rem", { lineHeight: "2.5rem" }],
      },

      /* -----------------------------------------------------------
         Spacing — 8px grid
         ----------------------------------------------------------- */
      spacing: {
        "18": "4.5rem",   // 72px
        "22": "5.5rem",   // 88px
        "sidebar": "280px",
        "sidebar-collapsed": "64px",
      },

      /* -----------------------------------------------------------
         Border radius — 12px standard
         ----------------------------------------------------------- */
      borderRadius: {
        DEFAULT: "12px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
      },

      /* -----------------------------------------------------------
         Max widths — content containers
         ----------------------------------------------------------- */
      maxWidth: {
        "content": "1280px",
        "reading": "960px",
      },

      /* -----------------------------------------------------------
         Animations
         ----------------------------------------------------------- */
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "slide-right": "slideRight 0.25s ease-out",
        "slide-left": "slideLeft 0.25s ease-out",
        "pulse-ring": "pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "shimmer": "shimmer 1.5s ease-in-out infinite",
        "star-pop": "star-pop 0.4s ease",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideRight: {
          "0%": { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        slideLeft: {
          "0%": { opacity: "0", transform: "translateX(10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },

      /* -----------------------------------------------------------
         Box shadow — layered for light theme
         ----------------------------------------------------------- */
      boxShadow: {
        "soft-sm": "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        "soft-md": "0 4px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)",
        "soft-lg": "0 8px 24px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)",
        card: "0 1px 2px rgba(28, 25, 23, 0.04), 0 1px 3px rgba(28, 25, 23, 0.06)",
        pop: "0 4px 12px rgba(28, 25, 23, 0.08), 0 2px 4px rgba(28, 25, 23, 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
