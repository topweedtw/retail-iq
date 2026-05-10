import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                bg: "#0b0d10",
                surface: "#111418",
                "surface-2": "#181c21",
                border: "#23272e",
                "text-primary": "#e6e8eb",
                "text-dim": "#8b949e",
                accent: "#7aa2ff",
                success: "#3fb950",
                warning: "#f0883e",
                danger: "#f85149",
            },
            fontFamily: {
                mono: ['"SF Mono"', '"JetBrains Mono"', "monospace"],
                sans: ['"SF Pro Text"', "-apple-system", '"Helvetica Neue"', "sans-serif"],
            },
        },
    },
    plugins: [],
};
export default config;
