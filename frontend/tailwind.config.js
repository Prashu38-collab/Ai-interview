/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Warm medium-tone paper backgrounds (neither dark nor stark white).
        paper: {
          DEFAULT: "#EFEAE1",
          soft: "#F6F2EB",
          card: "#FCF9F4",
          50: "#FAF7F0",
          100: "#F3EEE5",
          200: "#E9E1D2",
          300: "#D9CDB8",
          400: "#C3B396",
        },
        // Warm ink for text.
        ink: {
          DEFAULT: "#2B2721",
          soft: "#4A4439",
          muted: "#7A7263",
          faint: "#A49B89",
        },
        // Burnt copper accent — the one dominant color.
        brand: {
          50: "#FBF0E8",
          100: "#F6DEC9",
          200: "#EEBD94",
          300: "#E39A5F",
          400: "#D87A34",
          500: "#CB6218",
          600: "#B0510F",
          700: "#8F4210",
          800: "#743613",
          900: "#5E2D13",
        },
        // Sage green for positive states (kept warm, not neon).
        sage: {
          50: "#F0F5EF",
          100: "#DCE9DA",
          200: "#BAD2B8",
          300: "#93B792",
          400: "#6D9C6E",
          500: "#508150",
          600: "#3E673F",
          700: "#335333",
        },
        // Clay red for destructive / warnings.
        clay: {
          50: "#FBEFEC",
          100: "#F4D8D0",
          200: "#E7AFA0",
          300: "#D9826C",
          400: "#C75C40",
          500: "#AE4528",
          600: "#93371F",
          700: "#782D1B",
        },
      },
      fontFamily: {
        display: ["Fraunces Variable", "Georgia", "serif"],
        sans: ["Manrope Variable", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(43, 39, 33, 0.06), 0 8px 24px -12px rgba(43, 39, 33, 0.18)",
        lift: "0 2px 4px rgba(43, 39, 33, 0.08), 0 16px 32px -16px rgba(43, 39, 33, 0.28)",
      },
      backgroundImage: {
        "hero-grain":
          "radial-gradient(1200px 500px at 15% -10%, rgba(203, 98, 24, 0.14), transparent 55%), radial-gradient(900px 420px at 90% 0%, rgba(80, 129, 80, 0.12), transparent 50%), radial-gradient(700px 300px at 50% 110%, rgba(43, 39, 33, 0.06), transparent 60%)",
        "card-grain":
          "radial-gradient(600px 220px at 100% 0%, rgba(203, 98, 24, 0.07), transparent 60%)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pop-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "bar-fill": {
          "0%": { width: "0%" },
        },
      },
      animation: {
        rise: "rise 0.5s ease-out both",
        "pop-in": "pop-in 0.35s ease-out both",
        "bar-fill": "bar-fill 0.9s cubic-bezier(0.22, 1, 0.36, 1) both",
      },
    },
  },
  plugins: [],
};
