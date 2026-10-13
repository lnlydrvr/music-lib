/* Оверлей «?»: таблица горячих клавиш (классы .keymap* из styles.css).
   Открытое состояние живёт в overlays-сторе — с ним же работает подавление
   хоткеев и Esc в lib/hotkeys. */
import { useEffect, useRef } from "react";
import { useOverlays } from "../../stores/overlays";
import { useTranslation } from "react-i18next";
import type { TranslationKey } from "../../i18n/messages";

const ROWS: [key: string, descriptionKey: TranslationKey][] = [
  ["⌘K / Ctrl K", "dialogs.keymap.command"], ["1 … 6", "dialogs.keymap.navigation"], ["t", "dialogs.keymap.theme"], ["?", "dialogs.keymap.this_list"], ["Esc", "dialogs.keymap.dismiss"], ["Enter", "dialogs.keymap.enter"], ["j / k", "dialogs.keymap.next_track"],
];

export function KeymapDialog() {
  const { t } = useTranslation();
  const open = useOverlays((s) => s.keymapOpen);
  const setKeymapOpen = useOverlays((s) => s.setKeymapOpen);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        setKeymapOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>(
        "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
      ) ?? [])].filter((node) => !node.hasAttribute("disabled"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, setKeymapOpen]);

  useEffect(() => {
    if (open) return;
    const trigger = triggerRef.current;
    if (trigger?.isConnected) trigger.focus();
    triggerRef.current = null;
  }, [open]);

  useEffect(() => {
    document.body.classList.toggle("keymap-open", open);
    return () => document.body.classList.remove("keymap-open");
  }, [open]);

  return (
    <div id="keymap-root">
      {open && (
        <>
          <div className="keymap-backdrop" onClick={() => setKeymapOpen(false)} />
          <div ref={dialogRef} className="keymap" role="dialog" aria-modal="true" aria-label={t("dialogs.keymap.title")}>
            <h3 style={{ margin: "0 0 8px" }}>{t("dialogs.keymap.title")}</h3>
            <table>
              <tbody>
                {ROWS.map(([k, descriptionKey]) => (
                  <tr key={k}>
                    <td>
                      <span className="kbd">{k}</span>
                    </td>
                    <td>{t(descriptionKey)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 12, textAlign: "end" }}>
              <button ref={closeRef} className="ghost" type="button" onClick={() => setKeymapOpen(false)}>
                {t("dialogs.close")}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
