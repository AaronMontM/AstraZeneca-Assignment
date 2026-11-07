import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        az: {
          50: "#F8EDF3",
          100: "#F0D9E6",
          200: "#E2B5D0",
          300: "#CF87B1",
          400: "#B9508D",
          500: "#A02D70",
          600: "#830051",
          700: "#6D0045",
          800: "#570038",
          900: "#3D0029",
        },
        gold: {
          50: "#FFF9E8",
          100: "#FFF0C2",
          200: "#FDE18A",
          300: "#F7CD54",
          400: "#EFAB00",
          500: "#D99700",
          600: "#B77B00",
        },
        background: "#F8F7F9",
        surface: "#FFFFFF",
        sidebar: "#2B1425",
      },
      boxShadow: {
        card: "0 2px 12px rgba(45, 20, 38, 0.05)",
        elevated: "0 8px 30px rgba(45, 20, 38, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;