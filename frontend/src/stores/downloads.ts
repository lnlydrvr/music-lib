import { create } from "zustand";
import { get as apiGet } from "../lib/api";
import type { RenderableMessage } from "../i18n/messages";

export type DownloadStatus = "active" | "done" | "error";

export interface DownloadItem {
  id: string;
  title: RenderableMessage;
  /* Имя задачи с бэкенда: «Скачивание трека · Название». */
  name: RenderableMessage;
  status: DownloadStatus;
  percent: number | null;
  msg: RenderableMessage;
  addedAt: number;
  /* Анимация выхода (.out) перед фактическим удалением. */
  removing?: boolean;
  /* Автоскрытие успешных через 5 сек. */
  timer?: ReturnType<typeof setTimeout>;
}

interface JobRecord {
  id?: string;
  name?: RenderableMessage;
  status?: string;
  error?: RenderableMessage | null;
  created_at?: number;
}

interface DownloadsState {
  items: Record<string, DownloadItem>;
  expanded: boolean;
  track: (jobId: string, title: RenderableMessage) => void;
  progress: (jobId: string, d: { percent?: number | null; message?: RenderableMessage; msg?: RenderableMessage }) => void;
  finish: (jobId: string, ok: boolean, msg?: RenderableMessage) => void;
  dismiss: (jobId: string) => void;
  clearFinished: () => void;
  restore: () => Promise<void>;
  toggle: (force?: boolean) => void;
  titleFor: (endpoint: string, optsTitle?: RenderableMessage) => RenderableMessage;
  /* Завершённая задача из истории (restore): без авто-раскрытия дока. */
  renderDone: (jobId: string, title: RenderableMessage, ok: boolean, msg: RenderableMessage) => void;
}

const EXPANDED_KEY = "music-lib-dl-expanded";

/* Заголовки дока по эндпоинту запуска задачи. */
const TITLES: [prefix: string, title: RenderableMessage][] = [
  ["/api/ytmusic/download", { code: "jobs.ytm.name", message: "YouTube Music — download" }], ["/api/download/batch", { code: "jobs.download.batch_name", message: "Batch download" }], ["/api/download", { code: "jobs.download.name", message: "Download" }], ["/api/shazam/scan", { code: "jobs.shazam.scan_name", message: "Shazam — search" }], ["/api/recommend/generate", { code: "jobs.recommend.name", message: "Recommendations" }], ["/api/library/sort", { code: "jobs.library.sort_name", message: "Sort library" }], ["/api/lyrics/update-all", { code: "jobs.lyrics.name", message: "Update lyrics" }], ["/api/compress", { code: "jobs.compress.name", message: "Compression" }], ["/api/ytmusic/auth/browser/extract", { code: "jobs.auth.extract_name", message: "Extract browser cookies" }], ["/api/ytmusic/auth/browser/accounts", { code: "jobs.auth.accounts_name", message: "Find browser accounts" }], ["/api/ytmusic/auth/oauth", { code: "jobs.auth.oauth_name", message: "YouTube Music OAuth" }], ["/api/primuse/backfill", { code: "jobs.primuse.backfill_name", message: "Primuse — sidecars" }], ["/api/primuse/cleanup", { code: "jobs.primuse.cleanup_name", message: "Primuse — cleanup" }],
];

function readExpanded(): boolean {
  try {
    return localStorage.getItem(EXPANDED_KEY) === "1";
  } catch {
    return false;
  }
}

function writeExpanded(v: boolean): void {
  try {
    localStorage.setItem(EXPANDED_KEY, v ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export const useDownloads = create<DownloadsState>((set, get) => ({
  items: {},
  expanded: readExpanded(),

  titleFor(endpoint, optsTitle) {
    if (optsTitle) return optsTitle;
    const hit = TITLES.find(([p]) => endpoint.startsWith(p));
    return hit ? hit[1] : { code: "jobs.dock.fallback_name", message: "Background job" };
  },

  track(jobId, title) {
    if (get().items[jobId]) return;
    const item: DownloadItem = {
      id: jobId, title, name: "", status: "active", percent: null,
      msg: { code: "jobs.dock.launching", message: "Starting…" }, addedAt: Date.now(),
    };
    set((s) => ({ items: { ...s.items, [jobId]: item } }));
    // Имя задачи с бэкенда (точнее локального заголовка).
    apiGet<JobRecord>(`/api/jobs/${jobId}`)
      .then((st: JobRecord) => {
        const cur = get().items[jobId];
        if (st && st.name && cur) {
          set((s) => ({ items: { ...s.items, [jobId]: { ...cur, name: st.name! } } }));
        }
      })
      .catch(() => {});
    if (!get().expanded) get().toggle(true);
  },

  progress(jobId, d) {
    const item = get().items[jobId];
    if (!item || item.status !== "active") return;
    const next: Partial<DownloadItem> = {};
    if (d && d.percent != null) next.percent = d.percent;
    if (d && (d.message ?? d.msg)) next.msg = d.message ?? d.msg!;
    set((s) => ({ items: { ...s.items, [jobId]: { ...item, ...next } } }));
  },

  finish(jobId, ok, msg) {
    const item = get().items[jobId];
    if (!item) return;
    clearTimeout(item.timer);
    const next: DownloadItem = {
      ...item,
      status: ok ? "done" : "error",
      percent: ok ? 100 : 0,
      msg: msg || (ok ? { code: "jobs.common.done", message: "Done" } : { code: "jobs.common.failed", message: "Error" }),
    };
    if (ok) {
      // Автоскрытие успешных через 5 сек (выбор пользователя).
      next.timer = setTimeout(() => get().dismiss(jobId), 5000);
    }
    set((s) => ({ items: { ...s.items, [jobId]: next } }));
  },

  dismiss(jobId) {
    const item = get().items[jobId];
    if (!item || item.removing) return;
    clearTimeout(item.timer);
    // Короткая анимация .out, затем фактическое удаление из стора.
    set((s) => ({ items: { ...s.items, [jobId]: { ...item, removing: true } } }));
    setTimeout(() => {
      set((s) => {
        const items = { ...s.items };
        delete items[jobId];
        return { items };
      });
    }, 180);
  },

  clearFinished() {
    for (const [id, item] of Object.entries(get().items)) {
      if (item.status !== "active" && !item.removing) get().dismiss(id);
    }
  },

  async restore() {
    // Показываем хвост истории (ошибки + свежие готовые), активных подхватит startJob.
    let jobs: JobRecord[] = [];
    try {
      jobs = await apiGet<JobRecord[]>("/api/jobs", { limit: 10 });
    } catch {
      return;
    }
    const now = Date.now() / 1000;
    [...jobs].reverse().forEach((j) => {
      if (!j || !j.id || get().items[j.id]) return;
      if (j.status === "active" || j.status === "queued") return;
       if (j.status === "error") get().renderDone(j.id, j.name || { code: "jobs.dock.fallback_name", message: "Background job" }, false, j.error || { code: "jobs.common.failed", message: "Error" });
      else if (j.status === "done" && now - (j.created_at || 0) < 300) {
         get().renderDone(j.id, j.name || { code: "jobs.dock.fallback_name", message: "Background job" }, true, "");
      }
    });
  },

  renderDone(jobId, title, ok, msg) {
    if (get().items[jobId]) return;
    const item: DownloadItem = {
      id: jobId, title, name: "", status: ok ? "done" : "error",
       percent: ok ? 100 : 0, msg: msg || (ok ? { code: "jobs.common.done", message: "Done" } : { code: "jobs.common.failed", message: "Error" }),
      addedAt: Date.now(),
    };
    if (ok) item.timer = setTimeout(() => get().dismiss(jobId), 5000);
    set((s) => ({ items: { ...s.items, [jobId]: item } }));
  },

  toggle(force) {
    const expanded = force !== undefined ? !!force : !get().expanded;
    writeExpanded(expanded);
    set({ expanded });
  },
}));

/* Сортировка для рендера: свежие сверху (аналог prepend). */
export function downloadList(items: Record<string, DownloadItem>): DownloadItem[] {
  return Object.values(items).sort((a, b) => b.addedAt - a.addedAt);
}
