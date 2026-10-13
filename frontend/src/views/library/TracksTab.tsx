/* Вкладка «Треки»: единый список — локальные карточки (бейдж «♥ YT») и
   YT-треки без файла (лайки с «♥», «Радио», «↓»); панель деталей справа. */
import { forwardRef, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import clsx from "clsx";
import { VirtuosoGrid, type GridListProps, type VirtuosoGridHandle } from "react-virtuoso";
import { useTranslation } from "react-i18next";
import { RadioPanel } from "../../features/ytm/detail";
import { ytmDownload } from "../../features/ytm/download";
import type { YTMTrack } from "../../features/ytm/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { localeCmp, normKey, type SortMode, type TrackRow } from "./libUtils";
import { likedKeySet, TrackCard, YtTrackCard } from "./Cards";
import { showTrackDetailModal, TrackDetailBody, type TrackDetailActions } from "./trackDetail";
import type { YtApi } from "./useYtData";

function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(() =>
    typeof window.matchMedia === "function" ? window.matchMedia("(max-width: 900px)").matches : false,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(max-width: 900px)");
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

/* Порог виртуализации сетки: короткие списки — обычный div.lib-grid
   (и в jsdom без ResizeObserver), длинные — VirtuosoGrid. */
const GRID_VIRTUAL_THRESHOLD = 100;

export function TracksTab({
  items,
  list,
  sort,
  density,
  query,
  selected,
  toggleSelect,
  detailPath,
  onDetail,
  yt,
  actions,
  onCount,
}: {
  items: TrackRow[];
  list: TrackRow[];
  sort: SortMode;
  density: string;
  query: string;
  selected: Set<string>;
  toggleSelect: (path: string) => void;
  detailPath: string;
  onDetail: (path: string) => void;
  yt: YtApi;
  actions: TrackDetailActions;
  onCount: (node: ReactNode) => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage || i18n.language;
  const isNarrow = useIsNarrow();
  const gridRef = useRef<HTMLDivElement>(null);
  const [radioSeed, setRadioSeed] = useState<YTMTrack | null>(null);
  /* Лайки и «Библиотеку» аккаунта ждём параллельно; локальную сетку это не блокирует. */
  const [ytLiked, setYtLiked] = useState<YTMTrack[] | null>(null);
  const [ytLib, setYtLib] = useState<YTMTrack[] | null>(null);

  useEffect(() => {
    let alive = true;
    setYtLiked(null);
    setYtLib(null);
    Promise.all([yt.ytData<YTMTrack>("liked"), yt.ytData<YTMTrack>("library_songs")]).then(([liked, lib]) => {
      if (!alive) return;
      setYtLiked(liked);
      setYtLib(lib);
    });
    return () => {
      alive = false;
    };
  }, [yt]);

  /* Дедуп по video_id. */
  const ytAll = useMemo(() => {
    if (!ytLiked || !ytLib) return [];
    const seen = new Set<string>();
    const out: YTMTrack[] = [];
    for (const t of [...ytLiked, ...ytLib]) {
      if (!t.video_id || seen.has(t.video_id)) continue;
      seen.add(t.video_id);
      out.push(t);
    }
    return out;
  }, [ytLiked, ytLib]);

  const q = query.toLowerCase();
  const likedIds = useMemo(() => new Set((ytLiked || []).map((t) => t.video_id).filter(Boolean)), [ytLiked]);
  const likedKeys = useMemo(() => likedKeySet(ytLiked || []), [ytLiked]);
  const ytRows = useMemo(
    () =>
      ytAll.filter(
        (t) => !t.in_library && (!q || `${t.title || ""} ${t.artist || ""} ${t.album || ""}`.toLowerCase().includes(q)),
      ),
    [ytAll, q],
  );

  const baseCount =
    list.length !== items.length
      ? t("library.tracks.shown", { shown: list.length, total: items.length })
      : t("ytm.tracks.count", { count: items.length });
  useEffect(() => {
    if (list.length && ytRows.length) {
      onCount(
        <>
          {baseCount}
          <span className="lib-count-yt">{t("library.cloud.more", { count: ytRows.length })}</span>
        </>,
      );
    } else if (!list.length && ytRows.length) {
      onCount(t("library.cloud.only", { count: ytRows.length }));
    } else {
      onCount(baseCount);
    }
  }, [list.length, baseCount, ytRows.length, onCount, t]);

  /* Единый порядок локальных и облачных строк. Пока YT-данные не ответили
     (ytLiked/ytLib === null) — порядок API без локальной пересортировки:
     как первичный рендер library.js, сортировку делает бэкенд по текущему
     sort («По пути» — кодепоинтный порядок, а не ru-коллация localeCompare).
     После ответа (пусть и пустого) — общий localeCmp-порядок, как в легаси. */
  const ytReady = ytLiked !== null && ytLib !== null;
  const entries = useMemo(() => {
    type Entry = { key: string; t?: TrackRow; yt?: YTMTrack; title: string; artist: string; path: string; mtime: number; year: string; size: number };
    const arr: Entry[] = [
      ...list.map((t) => ({
        key: `l:${t.path}`,
        t,
        title: t.title || "",
        artist: t.artist || "",
        path: t.path,
        mtime: t.mtime || 0,
        year: t.year || "",
        size: t.size_bytes || 0,
      })),
      ...ytRows.map((t) => ({
        key: `y:${t.video_id}`,
        yt: t,
        title: t.title || "",
        artist: t.artist || "",
        path: t.video_id,
        mtime: 0,
        year: String(t.year || ""),
        size: 0,
      })),
    ];
    if (!ytReady) return arr;
    arr.sort((a, b) => {
      if (sort === "title") return localeCmp(a.title, b.title, locale) || localeCmp(a.artist, b.artist, locale);
      if (sort === "artist") return localeCmp(a.artist, b.artist, locale) || localeCmp(a.title, b.title, locale);
      if (sort === "added") return b.mtime - a.mtime || localeCmp(a.title, b.title, locale);
      if (sort === "year") return localeCmp(b.year, a.year, locale) || localeCmp(a.title, b.title, locale);
      if (sort === "size") return b.size - a.size || localeCmp(a.title, b.title, locale);
      return localeCmp(a.path, b.path, locale);
    });
    return arr;
  }, [list, ytRows, sort, ytReady, locale]);

  const detail = detailPath ? items.find((r) => r.path === detailPath) || null : null;
  /* Большие списки — VirtuosoGrid (окно скроллит страница). */
  const virtuosoRef = useRef<VirtuosoGridHandle>(null);
  const virtual = entries.length > GRID_VIRTUAL_THRESHOLD;

  /* Контейнер VirtuosoGrid — та же lib-grid с плотностью; style/ref
     обязательны (позиционирование айтемов). Пересоздаётся только при
     смене плотности. */
  const gridComponents = useMemo(
    () => ({
      List: forwardRef<HTMLDivElement, GridListProps>(function GridList({ className, children, ...rest }, ref) {
        return (
          <div ref={ref} {...rest} className={clsx("lib-grid", className)} data-density={density}>
            {children}
          </div>
        );
      }),
    }),
    [density],
  );

  /* Deep-link: подсветка и скролл к карточке (виртуально — по индексу). */
  useEffect(() => {
    if (!detailPath || isNarrow) return;
    if (virtual) {
      const idx = entries.findIndex((e) => e.path === detailPath);
      if (idx >= 0) virtuosoRef.current?.scrollToIndex({ index: idx, align: "center" });
      return;
    }
    const card = gridRef.current?.querySelector<HTMLElement>(`.lib-card[data-path="${CSS.escape(detailPath)}"]`);
    if (card?.scrollIntoView) card.scrollIntoView({ block: "center" });
  }, [detailPath, isNarrow, items, entries, virtual]);

  if (!list.length && !ytRows.length) {
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

  const renderEntry = ({ key, t, yt: ytr }: { key: string; t?: TrackRow; yt?: YTMTrack }) =>
    t ? (
      <TrackCard
        key={key}
        t={t}
        selected={selected.has(t.path)}
        active={detailPath === t.path}
        onToggleSelect={toggleSelect}
        onOpen={(tr) => {
          onDetail(tr.path);
          if (isNarrow) void showTrackDetailModal(tr, actions);
        }}
        ytBadge={likedKeys.has(normKey(t.artist, t.title))}
      />
    ) : ytr ? (
      <YtTrackCard
        key={key}
        t={ytr}
        liked={likedIds.has(ytr.video_id)}
        onRadio={setRadioSeed}
        onDownload={(x) => void ytmDownload([x], {
          kind: "track",
          providerId: x.video_id,
          title: { code: "jobs.ytm.name" },
        }, () => yt.refreshAfterYtDownload())}
      />
    ) : null;

  return (
    <div className="lib-wrap">
      {virtual ? (
        <VirtuosoGrid
          ref={virtuosoRef}
          useWindowScroll
          data={entries}
          computeItemKey={(_, e) => e.key}
          components={gridComponents}
          itemContent={(_, e) => renderEntry(e)}
          style={{ flex: 1, minWidth: 0 }}
        />
      ) : (
        <div className="lib-grid" data-density={density} ref={gridRef}>
          {entries.map(renderEntry)}
        </div>
      )}
      {!isNarrow ? (
        <div className="lib-detail">
          <h3>{t("library.detail.heading")}</h3>
          {detail ? <TrackDetailBody t={detail} actions={actions} /> : <div className="muted">{t("library.detail.choose_track")}</div>}
        </div>
      ) : null}
      {radioSeed ? (
        <RadioPanel seed={radioSeed} onClose={() => setRadioSeed(null)} onDownload={(items2, target) => ytmDownload(items2, target, () => yt.refreshAfterYtDownload())} />
      ) : null}
    </div>
  );
}
