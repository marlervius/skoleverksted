import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Calm, institutional accent — a muted petrol/teal. Deliberately not the
        // bright "AI blue", so the tool reads as a considered, trustworthy product.
        accent: {
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
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)"],
        mono: ["var(--font-geist-mono)"],
      },
      boxShadow: {
        // Subtle, flat elevation — no colored glows.
        card: "0 1px 2px rgba(28, 25, 23, 0.04), 0 1px 3px rgba(28, 25, 23, 0.06)",
        pop: "0 4px 12px rgba(28, 25, 23, 0.08), 0 2px 4px rgba(28, 25, 23, 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
