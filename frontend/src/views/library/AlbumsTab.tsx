/* Вкладка «Альбомы»: слияние локальных альбомов с YT-каталогом (полные ✓N/N,
   частичные N/M, нулевые — YT-карточка) и детали локального альбома. */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AlbumCard } from "../../features/ytm/cards";
import type { YTMAlbum } from "../../features/ytm/types";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  groupAlbums,
  normKey,
  sortAlbumGroups,
  localeCmp,
  type AlbumGroup,
  type SortMode,
  type TrackRow,
} from "./libUtils";
import { LocalAlbumCard, MergedAlbumCard } from "./Cards";
import { AlbumDetailLocal } from "./albumDetail";
import type { YtApi } from "./useYtData";

interface OrderEntry {
  key: string;
  g?: AlbumGroup;
  ya?: YTMAlbum;
  title: string;
  artist: string;
  path: string;
  year: string;
  mtime: number;
  size: number;
}

export function AlbumsTab({
  items,
  list,
  sort,
  density,
  nameTranslit,
  selected,
  toggleSelect,
  onOpenTrack,
  yt,
  openAlbumPaths,
  onOpenAlbum,
  onCloseAlbum,
  onOpenYtAlbum,
  onCount,
}: {
  items: TrackRow[];
  list: TrackRow[];
  sort: SortMode;
  density: string;
  nameTranslit: string;
  selected: Set<string>;
  toggleSelect: (path: string) => void;
  onOpenTrack: (t: TrackRow) => void;
  yt: YtApi;
  openAlbumPaths: string[] | null;
  onOpenAlbum: (g: AlbumGroup) => void;
  onCloseAlbum: () => void;
  onOpenYtAlbum: (id: string, name: string) => void;
  onCount: (node: ReactNode) => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage || i18n.language;
  const albums = useMemo(() => sortAlbumGroups(groupAlbums(list, locale), sort, locale), [list, sort, locale]);
  const totalAlbums = useMemo(() => groupAlbums(items, locale).length, [items, locale]);
  /* YT-двойники по ключам альбомов + дедуп-список альбомов аккаунта. */
  const [twins, setTwins] = useState<Map<string, YTMAlbum | null> | null>(null);
  const [ytAlbums, setYtAlbums] = useState<YTMAlbum[] | null>(null);
  const albumsKey = useMemo(() => albums.map((g) => g.key).join("|"), [albums]);

  useEffect(() => {
    let alive = true;
    setTwins(null);
    setYtAlbums(null);
    (async () => {
      const raw = await yt.ytData<YTMAlbum>("albums");
      if (!alive) return;
      const yseen = new Set<string>();
      const ytDedup: YTMAlbum[] = [];
      raw.forEach((ya) => {
        const k = normKey(ya.title, ya.artist);
        if (!yseen.has(k)) {
          yseen.add(k);
          ytDedup.push(ya);
        }
      });
      setYtAlbums(ytDedup);
      const ymap = new Map(ytDedup.map((ya) => [normKey(ya.title, ya.artist), ya]));
      // Двойников тянем параллельно, а не по одному.
      const found = await Promise.all(
        albums.map((g) => ymap.get(normKey(g.title, g.artist)) || yt.findAlbumTwin(g)),
      );
      if (!alive) return;
      setTwins(new Map(albums.map((g, i) => [g.key, found[i] ?? null])));
    })();
    return () => {
      alive = false;
    };
  }, [albumsKey, yt, albums]);

  /* Открытая деталь альбома: свежая группа по путям (фильтры могли измениться). */
  const openGroup = useMemo(
    () =>
      openAlbumPaths?.length
        ? albums.find((g) => g.paths.some((p) => openAlbumPaths.includes(p))) || null
        : null,
    [albums, openAlbumPaths],
  );

  const cloudOnly = useMemo(() => {
    if (!ytAlbums) return [];
    const localKeys = new Set(albums.map((g) => normKey(g.title, g.artist)));
    return ytAlbums.filter((ya) => !localKeys.has(normKey(ya.title, ya.artist)));
  }, [ytAlbums, albums]);

  const base =
    list.length !== items.length
      ? t("library.albums.shown", { shown: albums.length, total: totalAlbums })
      : t("library.albums.count", { count: albums.length });

  useEffect(() => {
    if (openGroup) {
      onCount(t("ytm.tracks.count", { count: openGroup.tracks.length }));
    } else if (albums.length && cloudOnly.length) {
      onCount(
        <>
          {base}
          <span className="lib-count-yt">{t("library.cloud.more", { count: cloudOnly.length })}</span>
        </>,
      );
    } else if (!albums.length && cloudOnly.length) {
      onCount(t("library.cloud.only", { count: cloudOnly.length }));
    } else {
      onCount(base);
    }
  }, [openGroup, base, albums.length, cloudOnly.length, onCount, t]);

  if (openGroup) {
    return (
      <AlbumDetailLocal
        g={openGroup}
        selected={selected}
        toggleSelect={toggleSelect}
        onBack={onCloseAlbum}
        onOpenTrack={onOpenTrack}
        yt={yt}
        actions={{ load: yt.refreshAfterYtDownload, openYtAlbum: onOpenYtAlbum }}
      />
    );
  }

  const hasCloud = (ytAlbums?.length || 0) > 0;
  if (!albums.length && !hasCloud) {
    return items.length ? (
      <div className="empty">{t("library.filters.no_results")}</div>
    ) : (
      <EmptyState
        title={t("library.empty")}
        sub={t("library.empty_hint")}
        action={
          <button className="btn-big" type="button" onClick={() => { location.hash = "#/discover/search"; }}>
            {t("home.find_music")}
          </button>
        }
      />
    );
  }

  /* Единый порядок: локальные + облачные, по режиму сортировки. */
  const order: OrderEntry[] = [
    ...albums.map((g) => ({
      key: normKey(g.title, g.artist),
      g,
      title: g.title,
      artist: g.artist,
      path: g.tracks[0]?.path || "",
      year: g.tracks[0]?.year || "",
      mtime: Math.max(...g.tracks.map((t) => t.mtime || 0)),
      size: g.tracks.reduce((n, t) => n + (t.size_bytes || 0), 0),
    })),
    ...(ytAlbums || [])
      .filter((ya) => !albums.some((g) => normKey(g.title, g.artist) === normKey(ya.title, ya.artist)))
      .map((ya) => ({
        key: normKey(ya.title, ya.artist),
        ya,
        title: ya.title || "",
        artist: ya.artist || "",
        path: "",
        year: String(ya.year || ""),
        mtime: 0,
        size: 0,
      })),
  ];
  order.sort((a, b) => {
    if (sort === "title") return localeCmp(a.title, b.title, locale) || localeCmp(a.artist, b.artist, locale);
    if (sort === "artist") return localeCmp(a.artist, b.artist, locale) || localeCmp(a.title, b.title, locale);
    if (sort === "added") return b.mtime - a.mtime || localeCmp(a.title, b.title, locale);
    if (sort === "year") return localeCmp(b.year, a.year, locale) || localeCmp(a.title, b.title, locale);
    if (sort === "size") return b.size - a.size || localeCmp(a.title, b.title, locale);
    return localeCmp(a.path || a.title, b.path || b.title, locale);
  });

  return (
    <div className="lib-grid" data-density={density}>
      {order.map(({ key, g, ya: cloudYa }) => {
        if (g) {
          const ya = twins?.get(g.key) ?? null;
          if (!ya) return <LocalAlbumCard key={key} g={g} onOpen={onOpenAlbum} />;
          const have = ya.in_library_tracks || 0;
          const total = ya.track_count || have;
          if (total && have >= total) return <LocalAlbumCard key={key} g={g} ya={ya} onOpen={onOpenAlbum} />;
          return (
            <MergedAlbumCard
              key={key}
              g={g}
              ya={ya}
              have={have}
              total={total}
              nameTranslit={nameTranslit}
              onOpen={onOpenAlbum}
            />
          );
        }
        if (!cloudYa) return null;
        return <AlbumCard key={key} album={cloudYa} onOpen={(a) => onOpenYtAlbum(a.id, a.title || "")} />;
      })}
    </div>
  );
}
