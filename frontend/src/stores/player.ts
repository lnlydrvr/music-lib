import { create } from "zustand";

export interface PlayerPlayOptions {
  src: string;
  title?: string;
  artist?: string;
  coverUrl?: string;
}

interface PlayerStore {
  src: string;
  title: string;
  artist: string;
  coverUrl: string;
  visible: boolean;
  /* Инкремент на каждый play(): повторный запуск того же src перезапускает
     воспроизведение (effect в AudioPlayer слушает [src, seq]). */
  seq: number;
  play: (opts: PlayerPlayOptions) => void;
  hide: () => void;
}

export const usePlayer = create<PlayerStore>((set, get) => ({
  src: "",
  title: "",
  artist: "",
  coverUrl: "",
  visible: false,
  seq: 0,
  play({ src, title, artist, coverUrl }) {
    if (!src) return;
    set({
      src,
      title: title || "",
      artist: artist || "",
      coverUrl: coverUrl || "",
      visible: true,
      seq: get().seq + 1,
    });
  },
  hide() {
    try {
      audioEl?.pause();
    } catch {
      /* ignore */
    }
    set({ visible: false });
  },
}));

/* --- Эмиттер событий плеера (замена PlayerBar.onAudio из старого SPA) --- */

const emitter = new EventTarget();
let audioEl: HTMLAudioElement | null = null;

const FORWARD_TYPES: (keyof HTMLMediaElementEventMap)[] = [
  "play", "pause", "ended", "timeupdate", "loadedmetadata",
];

function forward(e: Event) {
  // Новый объект: повторный dispatch исходного события InvalidStateError в jsdom.
  emitter.dispatchEvent(new Event(e.type));
}

/* Регистрация живого <audio> (PlayerBar/AudioPlayer): события форвардятся
   в эмиттер, доступный вьюхам без зависимости от DOM-компонента. */
export function attachAudio(el: HTMLAudioElement | null): void {
  if (audioEl === el) return;
  if (audioEl) FORWARD_TYPES.forEach((t) => audioEl!.removeEventListener(t, forward));
  audioEl = el;
  if (el) FORWARD_TYPES.forEach((t) => el.addEventListener(t, forward));
}

/* Подписка на play/pause/ended/... глобального плеера (подсветка кнопок
   превью). Возвращает отписку. */
export function onAudio(
  type: string,
  fn: (e: Event) => void,
  opts?: boolean | AddEventListenerOptions,
): () => void {
  emitter.addEventListener(type, fn, opts);
  return () => emitter.removeEventListener(type, fn, opts);
}

export function currentAudio(): HTMLAudioElement | null {
  return audioEl;
}
