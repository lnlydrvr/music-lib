/* Кэш данных YouTube Music для «Библиотеки»: ленивые запросы по видам,
   эпоха-сброс после скачивания (refreshAfterYtDownload), альбомы артистов
   и поиск YT-двойника локального альбома. */
import { useCallback, useRef, useState } from "react";
import { get } from "../../lib/api";
import type { YTMAlbum, YTMArtist } from "../../features/ytm";
import { normKey, normOne, type AlbumGroup } from "./libUtils";

export type YtKind = "albums" | "artists" | "liked" | "library_songs" | "playlists";

const ENDPOINTS: Record<YtKind, [ep: string, key: string, limit: number]> = {
  albums: ["/api/ytmusic/albums", "albums", 400],
  artists: ["/api/ytmusic/artists", "artists", 400],
  liked: ["/api/ytmusic/liked", "tracks", 500],
  library_songs: ["/api/ytmusic/library_songs", "tracks", 500],
  playlists: ["/api/ytmusic/playlists", "playlists", 400],
};

export function useYtData(load: () => Promise<void>) {
  const cache = useRef<Partial<Record<YtKind, unknown[]>>>({});
  const pending = useRef<Partial<Record<YtKind, Promise<unknown[]>>>>({});
  const artistAlbums = useRef<Record<string, Promise<YTMAlbum[]>>>({});
  const epoch = useRef(0);
  const connectedRef = useRef<boolean | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  /* Эпоха в state: вкладки перезапускают YT-эффекты после сброса кэша. */
  const [epochState, setEpochState] = useState(0);

  const ytData = useCallback(<T>(kind: YtKind): Promise<T[]> => {
    if (connectedRef.current === false) return Promise.resolve([]);
    const hit = cache.current[kind];
    if (hit != null) return Promise.resolve(hit as T[]);
    const inflight = pending.current[kind];
    if (inflight) return inflight as Promise<T[]>;
    const [ep, key, limit] = ENDPOINTS[kind];
    const myEpoch = epoch.current;
    const req = (async () => {
      try {
        const res = await get<Record<string, T[]>>(ep, { limit });
        if (myEpoch === epoch.current) cache.current[kind] = res[key] || [];
      } catch {
        // Не подключён / нет сети: считаем YT недоступным до пересброса.
        if (myEpoch === epoch.current) {
          connectedRef.current = false;
          setConnected(false);
          cache.current[kind] = [];
        }
      }
      return myEpoch === epoch.current ? (cache.current[kind] as T[]) : [];
    })();
    pending.current[kind] = req;
    req.finally(() => {
      if (pending.current[kind] === req) delete pending.current[kind];
    });
    return req;
  }, []);

  /* Альбомы артиста из его страницы (кэш по browse_id): двойники локальных
     альбомов, которых нет в «сохранённых альбомах» аккаунта. */
  const ytArtistAlbums = useCallback((id: string): Promise<YTMAlbum[]> => {
    if (!artistAlbums.current[id]) {
      artistAlbums.current[id] = get<{ albums?: YTMAlbum[] }>("/api/ytmusic/artist", { browse_id: id })
        .then((d) => d.albums || [])
        .catch(() => []);
    }
    return artistAlbums.current[id];
  }, []);

  /* Найти YT-двойник локального альбома: сначала в сохранённых альбомах
     аккаунта, затем через альбомы подписанного исполнителя. */
  const findAlbumTwin = useCallback(
    async (g: AlbumGroup): Promise<YTMAlbum | null> => {
      const saved = (await ytData<YTMAlbum>("albums")).find(
        (ya) => normKey(ya.title, ya.artist) === normKey(g.title, g.artist || ""),
      );
      if (saved) return saved;
      const artists = await ytData<YTMArtist>("artists");
      const ar = artists.find((a) => normOne(a.name) === normOne(g.artist || ""));
      if (!ar) return null;
      const albums = await ytArtistAlbums(ar.id);
      return albums.find((al) => normKey(al.title, al.artist) === normKey(g.title, g.artist || "")) || null;
    },
    [ytData, ytArtistAlbums],
  );

  /* После загрузки из YT: сбросить кэш и дедуп, перечитать библиотеку. */
  const refreshAfterYtDownload = useCallback(async () => {
    epoch.current += 1;
    connectedRef.current = null;
    setConnected(null);
    cache.current = {};
    pending.current = {};
    artistAlbums.current = {};
    setEpochState(epoch.current);
    await load();
  }, [load]);

  return { ytData, findAlbumTwin, ytArtistAlbums, refreshAfterYtDownload, connected, epoch: epochState };
}

export type YtApi = ReturnType<typeof useYtData>;
