import { useEffect } from "react";
import { useOverlays } from "../stores/overlays";
import type { RouteName } from "../routes";

const NAV_KEYS: Record<string, RouteName> = {
  "1": "menu",
  "2": "library",
  "3": "discover",
  "4": "recommend",
  "5": "quality",
  "6": "settings",
};

/* Тема: t на латинице + е/т в русской раскладке (клавиша T = «е», старый код
   слушал t/T/е/Е; «т» добавлена как буквенная пара). */
const THEME_KEYS = new Set(["t", "T", "т", "Т", "е", "Е"]);

/* j/k: фокус по строкам/карточкам списков. */
function stepFocus(dir: number, e: KeyboardEvent) {
  const root = document.getElementById("view");
  const items = [...(root?.querySelectorAll<HTMLElement>(".trackrow, .lib-card, .batch-item") ?? [])].filter(
    (n) => n.offsetParent !== null,
  );
  if (!items.length) return;
  e.preventDefault();
  const idx = items.indexOf(document.activeElement as HTMLElement);
  const next = items[(idx + dir + items.length) % items.length];
  if (next) next.focus();
}

/* Глобальные хоткеи: навигация 1–6, тема, j/k, «?» — таблица клавиш,
   Cmd/Ctrl+K — палитра команд. Под модалкой/keymap/палитрой хоткеи вью
   молчат: цифры и t не должны переставлять экран и терять несохранённое
   редактирование. */
export function useHotkeys({ onToggleTheme }: { onToggleTheme: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      /* ⌘K / Ctrl+K — до раннего return по модификаторам. Проверяем и code:
         с Cmd на не-латинской раскладке e.key приходит не «k». */
      if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key.toLowerCase() === "k" || e.code === "KeyK")) {
        e.preventDefault();
        const o = useOverlays.getState();
        o.setCommandOpen(!o.commandOpen);
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      const tag = t?.tagName || "";
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag) || t?.isContentEditable) {
        if (e.key === "Escape") t?.blur();
        return;
      }
      const overlays = useOverlays.getState();
      const overlayOpen = overlays.dialogCount > 0 || overlays.keymapOpen || overlays.commandOpen;
      if (e.key === "?" && !overlayOpen) {
        e.preventDefault();
        overlays.setKeymapOpen(true);
        return;
      }
      if (e.key === "Escape") {
        if (overlays.keymapOpen) overlays.setKeymapOpen(false);
        else if (overlays.commandOpen) overlays.setCommandOpen(false);
        return;
      }
      if (overlayOpen) return;
      if (e.key === "j" || e.key === "k") {
        stepFocus(e.key === "j" ? 1 : -1, e);
        return;
      }
      if (THEME_KEYS.has(e.key)) onToggleTheme();
      const dest = NAV_KEYS[e.key];
      if (dest) location.hash = "#/" + dest;
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onToggleTheme]);
}
