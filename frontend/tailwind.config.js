/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0b0f1a",
        surface: "#141a2b",
        surface2: "#1b2338",
        border: "#232a3d",
        fg: "#e6e9f0",
        muted: "#9aa4bd",
        brand: {
          DEFAULT: "#7c3aed",
          600: "#6d28d9",
          500: "#7c3aed",
          400: "#8b5cf6",
        },
        accent: "#22d3ee",
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.25)",
      },
      backgroundImage: {
        brand: "linear-gradient(135deg,#7c3aed,#4f46e5)",
      },
    },
  },
  plugins: [],
}
