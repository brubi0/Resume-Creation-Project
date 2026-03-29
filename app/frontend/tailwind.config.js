/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#3d5a80",
          mid: "#98c1d9",
          light: "#e0fbfc",
          gold: "#e9c46a",
          coral: "#e76f51",
          green: "#52b788",
        },
      },
    },
  },
  plugins: [],
};
