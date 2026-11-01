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
        background: "#FFE14D", // Pop yellow
        surface: "#FFFFFF",    // Pure white
        border: "#000000",
        primary: "#FF4FA3",   // Brutalist Pink
        mint: "#35F28A",      // Small tier / savings / good
        orange: "#FF9F1C",    // Medium tier / warnings / fallback
        lavender: "#B388FF",  // Large tier / safety / quality
        danger: "#FF3B30",    // Errors / dead letter / poor
        dangerText: "#B91C1C",
        muted: "#333333",
        focusTint: "#FFF8CC",
      },
      fontFamily: {
        heading: ["'Archivo Black'", "sans-serif"],
        mono: ["'Space Mono'", "monospace"],
      },
      boxShadow: {
        card: "8px 8px 0px #000000",
        btn: "4px 4px 0px #000000",
        btnHover: "6px 6px 0px #000000",
        badge: "3px 3px 0px #000000",
        err: "6px 6px 0px #000000",
      },
    },
  },
  plugins: [],
};

export default config;
