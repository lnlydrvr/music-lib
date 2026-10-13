import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = `http://127.0.0.1:${process.env.MUSIC_LIB_DEV_PORT || 8765}`;

/* Имя npm-пакета из id модуля: ".../node_modules/@scope/pkg/..." → "@scope/pkg".
   Совпадение по полному имени пакета, а не подстроке — «react» не ловит «react-dom»-соседей. */
function pkgName(id: string): string | null {
  const m = id.match(/[\\/]node_modules[\\/]((?:@[^\\/]+[\\/])?[^\\/]+)/);
  return m ? m[1] : null;
}

/* Vendor-гранулы: стабильные (перекэшируются между релизами) и по одному сценарию
   загрузки. Транзитивные зависимости отнесены к графу, который их тянет:
   scheduler — react-dom; floating-ui/reselect/tabbable/... — только @base-ui. */
const CHUNK_REACT = new Set(["react", "react-dom", "scheduler"]);
const CHUNK_UI = new Set([
  "@base-ui-components/react",
  "@base-ui-components/utils",
  "class-variance-authority",
  "clsx",
  "@babel/runtime",
  "@floating-ui/react-dom",
  "@floating-ui/utils",
  "reselect",
  "tabbable",
  "use-sync-external-store",
]);
const CHUNK_STATE = new Set(["zustand", "sonner"]);

/* Код приложения: всё, кроме экранов (src/views/**), — один общий чанк «app»
   (он же entry). Экраны грузятся через React.lazy и остаются отдельными
   чанками, а их общий код (lib/, stores/, features/editor, features/ytm,
   ui-кит) не дробится на горстку общих кусочков по 0.3 КБ, а живёт в основном
   чанке. */
const SRC_DIR = new URL("./src/", import.meta.url).pathname;

function appChunk(id: string): "app" | undefined {
  return id.slice(SRC_DIR.length).startsWith("views/") ? undefined : "app";
}

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/web/dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const pkg = pkgName(id);
          if (pkg) {
            if (CHUNK_REACT.has(pkg)) return "react";
            if (CHUNK_UI.has(pkg)) return "ui";
            if (CHUNK_STATE.has(pkg)) return "state";
            return undefined; // прочие пакеты — вместе с кодом приложения
          }
          if (id.startsWith(SRC_DIR)) return appChunk(id);
          return undefined;
        },
      },
    },
  },
  server: {
    // IPv4-localhost: Vite по умолчанию слушает только ::1, а бэкенд — 127.0.0.1.
    host: "127.0.0.1",
    proxy: {
      // API бэкенда; http-proxy стримит ответы без буферизации — SSE (EventSource,
      // /api/jobs/*/events) работает, у uvicorn нет gzip поверх стрима.
      "/api": {
        target: backend,
        changeOrigin: true,
      },
    },
  },
});
