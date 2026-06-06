import type { Config } from "tailwindcss";
import { pasTokens } from "./src/lib/designKit";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}", "./tests/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: pasTokens.color,
      borderRadius: pasTokens.radius,
      spacing: pasTokens.spacing,
      fontFamily: {
        sans: [pasTokens.typography.font],
      },
      letterSpacing: {
        body: pasTokens.typography.bodyLetterSpacing,
      },
      lineHeight: {
        body: pasTokens.typography.bodyLineHeight,
      },
    },
  },
} satisfies Config;
