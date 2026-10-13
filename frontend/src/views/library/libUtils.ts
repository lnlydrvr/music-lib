/* Утилиты экрана «Библиотека»: нормализация имён, группировка альбомов,
   общие значения тегов (порт library.js). */
import { fmtSize } from "../../lib/format";
import i18n from "../../i18n";

export interface TrackRow {
  path: string;
  artist: string;
  album: string;
  title: string;
  year: string;
  genre: string;
  album_artist: string;
  isrc: string;
  composer: string;
  track_number: string;
  disc_number: string;
  size_bytes: number;
  duration_seconds: number;
  bitrate: number;
  mtime: number;
  has_lyrics: boolean;
  has_synced_lyrics: boolean;
  has_cover: boolean;
  ext: string;
  need_compress?: boolean;
  compress_size_bytes?: number;
}

export interface AlbumGroup {
  key: string;
  title: string;
  artist: string;
  paths: string[];
  tracks: TrackRow[];
  coverPath: string | null;
}

export type SortMode = "path" | "title" | "artist" | "added" | "year" | "size";

export function stemOf(p: string): string {
  const base = p.split("/").pop() || p;
  return base.replace(/\.[^.]+$/, "");
}

/* Кириллица→латиница (как `_norm` в src/ytmusic.py), чтобы локальная запись
   «Валентин Стрыкало» совпадала с подпиской YT Music «Valentin Strykalo». */
const CYR2LAT: Record<string, string> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e",
  ж: "zh", з: "z", и: "i", й: "i", к: "k", л: "l", м: "m",
  н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u",
  ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh", щ: "shch",
  ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
};

export function normOne(s: unknown): string {
  const low = String(s || "").toLowerCase();
  let out = "";
  for (const ch of low) out += CYR2LAT[ch] != null ? CYR2LAT[ch] : ch;
  return out.replace(/[^a-z0-9]/gi, "");
}

export function normKey(a: unknown, b: unknown): string {
  return normOne(a) + "::" + normOne(b);
}

/* Имя для пары «локальная кириллица + YT-латиница» по настройке name_translit. */
export function pickName(cyr: string, lat: string, mode: string): string {
  if (mode === "cyrillic") return cyr || lat;
  if (mode === "latin") return lat || cyr;
  return lat || cyr;
}

export function localeCmp(a: unknown, b: unknown, locale: string): number {
  return String(a || "").localeCompare(String(b || ""), locale, { sensitivity: "base", numeric: true });
}

/* Группировка треков в альбомы (безальбомные — синглы по одному). */
export function groupAlbums(list: TrackRow[], locale: string): AlbumGroup[] {
  const map = new Map<string, AlbumGroup>();
  list.forEach((t) => {
    const album = (t.album || "").trim();
    if (!album) {
      const key = "single::" + t.path;
      if (!map.has(key)) {
        map.set(key, {
          key,
          title: t.title || stemOf(t.path),
          artist: t.artist || "",
          paths: [t.path],
          tracks: [t],
          coverPath: t.has_cover ? t.path : null,
        });
      }
      return;
    }
    const alArt = (t.album_artist || "").trim() || (t.artist || "").trim();
    const key = "album::" + album.toLowerCase() + "::" + alArt.toLowerCase();
    let g = map.get(key);
    if (!g) {
      g = { key, title: album, artist: alArt, paths: [], tracks: [], coverPath: null };
      map.set(key, g);
    }
    g.paths.push(t.path);
    g.tracks.push(t);
    if (!g.coverPath && t.has_cover) g.coverPath = t.path;
  });
  const numPrefix = (v: unknown) => {
    const m = String(v || "").match(/\d+/);
    return m ? parseInt(m[0], 10) : 0;
  };
  const out = [...map.values()];
  out.forEach((g) =>
    g.tracks.sort(
      (a, b) =>
        numPrefix(a.disc_number) - numPrefix(b.disc_number) ||
        numPrefix(a.track_number) - numPrefix(b.track_number) ||
         localeCmp(a.disc_number, b.disc_number, locale) ||
         localeCmp(a.track_number, b.track_number, locale) ||
         localeCmp(a.title, b.title, locale),
    ),
  );
  return out;
}

export function sortAlbumGroups(groups: AlbumGroup[], mode: SortMode, locale: string): AlbumGroup[] {
  const out = [...groups];
  out.sort((a, b) => {
    if (mode === "title") return localeCmp(a.title, b.title, locale) || localeCmp(a.artist, b.artist, locale);
    if (mode === "artist") return localeCmp(a.artist, b.artist, locale) || localeCmp(a.title, b.title, locale);
    if (mode === "added") return (b.tracks[0]?.mtime || 0) - (a.tracks[0]?.mtime || 0) || localeCmp(a.title, b.title, locale);
    if (mode === "year") return localeCmp(b.tracks[0]?.year || "", a.tracks[0]?.year || "", locale) || localeCmp(a.title, b.title, locale);
    if (mode === "size") {
      return (
          b.tracks.reduce((n, t) => n + (t.size_bytes || 0), 0) -
            a.tracks.reduce((n, t) => n + (t.size_bytes || 0), 0) || localeCmp(a.title, b.title, locale)
      );
    }
    return localeCmp(a.tracks[0]?.path || "", b.tracks[0]?.path || "", locale);
  });
  return out;
}

/* Поля массового редактора «Общие теги альбома»: всё, что поддерживает
   POST /api/tags/apply, кроме title/track_number/disc_number и обложки. */
export const ALBUM_COMMON_TAG_FIELDS = [
  "artist", "album", "album_artist", "year", "genre", "isrc", "composer", "publisher", "comment",
] as const;

/* Общее значение поля по трекам альбома: непустые совпадают → значение;
   различаются → null; пусто → "". */
export function albumCommonValue(tracks: TrackRow[], field: string): string | null {
  let val = "";
  let seen = false;
  for (const t of tracks) {
    const v = String((t as unknown as Record<string, unknown>)[field] || "").trim();
    if (!v) continue;
    if (seen && v !== val) return null;
    val = v;
    seen = true;
  }
  return seen ? val : "";
}

export function compressLabel(t: TrackRow): string {
  return t.need_compress
    ? i18n.t("library.compress.needed", { before: fmtSize(t.size_bytes), after: fmtSize(t.compress_size_bytes) })
    : i18n.t("library.compress.ok");
}
