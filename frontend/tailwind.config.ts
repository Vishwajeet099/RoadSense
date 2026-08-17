import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        asphalt: "#202124",
        lane: "#f7c948",
        signal: "#0f766e",
        alert: "#dc2626",
      },
    },
  },
  plugins: [],
};

export default config;
