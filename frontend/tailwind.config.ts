import type { Config } from "tailwindcss";

/**
 * Scholar design system — "modern scholarly" (a refined digital reading room).
 *
 * Tokens mirror the CSS variables declared in src/app/globals.css. Color values
 * are duplicated here as literals so utility classes work without runtime vars,
 * while the CSS variables drive base element styling. Light theme only.
 */
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Confident indigo/violet primary scale.
        primary: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5", // primary
          700: "#4338ca", // hover/active
          800: "#3730a3",
          900: "#312e81",
        },
        // Warm, paper-like neutral surfaces (slightly warm grays / near-white).
        surface: {
          DEFAULT: "#faf9f7", // app background — warm near-white
          subtle: "#f6f5f2", // recessed panels
          card: "#ffffff", // raised cards
          border: "#e8e6e1", // soft warm borders
          ring: "#dcd9d2", // stronger divider / focus track
        },
        // Warm-tinted ink for text.
        ink: {
          DEFAULT: "#1c1a17", // headings / primary text
          soft: "#4a463f", // body text
          muted: "#8a857b", // secondary / captions
        },
        // Semantic status colors.
        success: {
          50: "#ecfdf5",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
        },
        warning: {
          50: "#fffbeb",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
        },
        danger: {
          50: "#fef2f2",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
        },
        info: {
          50: "#eff6ff",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
      },
      fontFamily: {
        // Wired to next/font CSS variables set in layout.tsx.
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      borderRadius: {
        xl: "0.875rem", // 14px — default card radius
        "2xl": "1.25rem", // 20px — large surfaces
      },
      boxShadow: {
        // Soft, low-contrast elevation tuned for warm surfaces.
        soft: "0 1px 2px rgba(28, 26, 23, 0.04), 0 1px 3px rgba(28, 26, 23, 0.06)",
        card: "0 1px 3px rgba(28, 26, 23, 0.05), 0 4px 12px rgba(28, 26, 23, 0.05)",
        lift: "0 4px 8px rgba(28, 26, 23, 0.06), 0 12px 28px rgba(28, 26, 23, 0.08)",
        focus: "0 0 0 3px rgba(79, 70, 229, 0.25)",
      },
    },
  },
  plugins: [],
};
export default config;
