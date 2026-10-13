import { create } from "zustand";

/* Оверлеи, подавляющие хоткеи вью: открытые диалоги (счётчиком — их может
   монтировать/размонтировать base-ui), таблица горячих клавиш и ⌘K-палитра. */
interface OverlaysState {
  dialogCount: number;
  keymapOpen: boolean;
  commandOpen: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  setKeymapOpen: (v: boolean) => void;
  setCommandOpen: (v: boolean) => void;
}

export const useOverlays = create<OverlaysState>((set) => ({
  dialogCount: 0,
  keymapOpen: false,
  commandOpen: false,
  openDialog: () => set((s) => ({ dialogCount: s.dialogCount + 1 })),
  closeDialog: () => set((s) => ({ dialogCount: Math.max(0, s.dialogCount - 1) })),
  setKeymapOpen: (v) => set({ keymapOpen: v }),
  setCommandOpen: (v) => set({ commandOpen: v }),
}));

/* Для вне-React кода (hotkeys, Esc-обработчики). */
export function anyOverlayOpen(): boolean {
  const s = useOverlays.getState();
  return s.dialogCount > 0 || s.keymapOpen || s.commandOpen;
}
