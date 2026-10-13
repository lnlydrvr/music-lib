import { defineConfig } from "vitest/config";

/* Конфиг тестов отдельно от vite.config: jsdom + RTL, без dev-прокси. */
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
  },
});
