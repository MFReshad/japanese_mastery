import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./features/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201a",
        moss: "#3c6f57",
        persimmon: "#d85d3c",
        paper: "#faf8f3",
      },
    },
  },
  plugins: [],
};

export default config;
