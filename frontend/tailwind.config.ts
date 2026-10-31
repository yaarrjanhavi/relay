import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#000000",
        surface: "#1A1A1A",
        surfaceHover: "#222222",
        border: "#262626",
        primary: {
          DEFAULT: "#3DFF6B",
          dark: "#2ecc55",
          light: "#64ff8b",
        },
        accent: {
          DEFAULT: "#A855F7",
          dark: "#9333ea",
          light: "#c084fc",
        },
        muted: "#888888",
        danger: "#EF4444",
      },
      fontFamily: {
        heading: ["Teko", "sans-serif"],
        sans: ["Urbanist", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
