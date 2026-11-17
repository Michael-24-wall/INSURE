/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f5f8fc",
          100: "#e9eff7",
          200: "#d7e2ef",
          300: "#b7c9de",
          400: "#8ba6c4",
          500: "#64748b",
          600: "#47617f",
          700: "#33475e",
          800: "#24354b",
          900: "#172b4d",
          950: "#0f1f38"
        },
        brand: {
          50: "#eaf2fc",
          100: "#d6e6f8",
          200: "#a9cbf0",
          300: "#7aabe4",
          400: "#4a8bd5",
          500: "#2868b2",
          600: "#174a8b",
          700: "#133d72",
          800: "#102f59",
          900: "#0c2546",
          950: "#081a33"
        },
        accent: {
          50: "#fff6ee",
          100: "#ffead5",
          200: "#ffd2a8",
          300: "#fdb370",
          400: "#fa8d38",
          500: "#f47b20",
          600: "#e2640f",
          700: "#bb4c0f",
          800: "#953d14",
          900: "#783413",
          950: "#411806"
        },
        navy: {
          300: "#7ca3d4",
          400: "#4d7cbd",
          500: "#174a8b",
          600: "#123d74",
          700: "#0e305c"
        },
        lime: {
          300: "#e2fb8a",
          400: "#d0f45c",
          500: "#b9e62e"
        },
        sand: {
          50: "#faf9f5",
          100: "#f3f0e7",
          200: "#e7e1d2"
        }
      },
      fontFamily: {
        sans: ["Aptos", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
        display: ["Aptos Display", "Segoe UI", "system-ui", "sans-serif"]
      },
      boxShadow: {
        soft: "0 18px 50px -24px rgba(7, 22, 29, 0.35)",
        card: "0 1px 2px rgba(7, 22, 29, 0.04), 0 12px 32px -24px rgba(7, 22, 29, 0.35)"
      },
      borderRadius: {
        "4xl": "2rem"
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: 0, transform: "translateY(16px)" },
          "100%": { opacity: 1, transform: "translateY(0)" }
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" }
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.85)", opacity: 0.7 },
          "75%, 100%": { transform: "scale(1.6)", opacity: 0 }
        }
      },
      animation: {
        "fade-up": "fade-up 0.6s ease both",
        float: "float 6s ease-in-out infinite",
        "pulse-ring": "pulse-ring 2s ease-out infinite"
      }
    }
  },
  plugins: []
};
