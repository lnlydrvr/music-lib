/* Вкладка «Исполнители»: локальные + YT-подписки (двойники заменяют карточки,
   остальные добавляются); клик — детали исполнителя (YT или локальная страница). */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { coverUrl } from "../../lib/api";
import { useTranslation } from "react-i18next";
import { ArtistCard } from "../../features/ytm/cards";
import type { YTMArtist } from "../../features/ytm/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { normOne, pickName, localeCmp, type SortMode, type TrackRow } from "./libUtils";
import { LocalArtistCard } from "./Cards";
import type { YtApi } from "./useYtData";

export function ArtistsTab({
  items,
  list,
  sort,
  density,
  nameTranslit,
  query,
  yt,
  onOpenLocalArtist,
  onOpenYtArtist,
  onCount,
}: {
  items: TrackRow[];
  list: TrackRow[];
  sort: SortMode;
  density: string;
  nameTranslit: string;
  query: string;
  yt: YtApi;
  onOpenLocalArtist: (name: string) => void;
  onOpenYtArtist: (id: string, name: string, localName: string) => void;
  onCount: (node: ReactNode) => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage || i18n.language;
  /* Локальные исполнители — сразу, до ответа YouTube Music. */
  const localArr = useMemo(() => {
    const amap = new Map<string, { name: string; count: number; coverPath: string | null }>();
    list.forEach((t) => {
      if (!t.artist) return;
      const k = normOne(t.artist);
      let e = amap.get(k);
      if (!e) {
        e = { name: t.artist, count: 0, coverPath: null };
        amap.set(k, e);
      }
      e.count += 1;
      if (!e.coverPath && t.has_cover) e.coverPath = t.path;
    });
    const arr = [...amap.values()];
    if (sort === "title" || sort === "path") arr.sort((a, b) => localeCmp(a.name, b.name, locale));
    else arr.sort((a, b) => b.count - a.count || localeCmp(a.name, b.name, locale));
    return arr;
  }, [list, sort, locale]);

  const q = query.toLowerCase();
  const shown = useMemo(() => localArr.filter((a) => !q || a.name.toLowerCase().includes(q)), [localArr, q]);

  const [ytArtists, setYtArtists] = useState<YTMArtist[] | null>(null);
  useEffect(() => {
    let alive = true;
    setYtArtists(null);
    yt.ytData<YTMArtist>("artists").then((yta) => {
      if (!alive) return;
      const yseen = new Set<string>();
      const ytDedup: YTMArtist[] = [];
      yta.forEach((ya) => {
        const k = normOne(ya.name);
        if (!yseen.has(k)) {
          yseen.add(k);
          ytDedup.push(ya);
        }
      });
      setYtArtists(ytDedup);
    });
    return () => {
      alive = false;
    };
  }, [yt]);

  const ymap = useMemo(() => new Map((ytArtists || []).map((ya) => [normOne(ya.name), ya])), [ytArtists]);
  const localKeys = useMemo(() => new Set(shown.map((a) => normOne(a.name))), [shown]);
  const cloudOnly = useMemo(
    () => (ytArtists || []).filter((ya) => !localKeys.has(normOne(ya.name))),
    [ytArtists, localKeys],
  );

  useEffect(() => {
    if (shown.length && cloudOnly.length) {
      onCount(
        <>
          {t("library.artists.count", { count: shown.length })}
          <span className="lib-count-yt">{t("library.cloud.more", { count: cloudOnly.length })}</span>
        </>,
      );
    } else if (!shown.length && cloudOnly.length) {
      onCount(t("library.cloud.only", { count: cloudOnly.length }));
    } else {
      onCount(t("library.artists.count", { count: shown.length }));
    }
  }, [shown.length, cloudOnly.length, onCount, t]);

  const hasCloud = (ytArtists?.length || 0) > 0;
  if (!shown.length && !hasCloud) {
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

  return (
    <div className="lib-grid" data-density={density}>
      {shown.map((a) => {
        const ya = ymap.get(normOne(a.name));
        if (!ya) return <LocalArtistCard key={normOne(a.name)} a={a} onOpen={onOpenLocalArtist} />;
        const name = pickName(a.name, ya.name || "", nameTranslit);
        return (
          <ArtistCard
            key={normOne(a.name)}
            artist={{
              id: ya.id,
              name,
              subscribers: ya.subscribers,
              cover_url: a.coverPath ? coverUrl(a.coverPath) : ya.cover_url || "",
              local_count: a.count,
            }}
            subscribed
            onOpen={() => onOpenYtArtist(ya.id, name, a.name)}
          />
        );
      })}
      {(ytArtists || [])
        .filter((ya) => !localKeys.has(normOne(ya.name)))
        .map((ya) => (
          <ArtistCard
            key={`yt-${normOne(ya.name)}`}
            artist={{
              id: ya.id,
              name: ya.name,
              subscribers: ya.subscribers,
              cover_url: ya.cover_url || "",
              local_count: ya.local_count || 0,
            }}
            subscribed
            onOpen={() => onOpenYtArtist(ya.id, ya.name || "", ya.name || "")}
          />
        ))}
    </div>
  );
}
