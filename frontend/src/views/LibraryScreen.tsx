/* Библиотека: 4 вкладки (Альбомы / Треки / Исполнители / Плейлисты),
   фильтры, выбор, действия тулбара, Inbox и deep-link ?path=. */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../i18n/messages";
import { get, post } from "../lib/api";
import { toast } from "../lib/toast";
import { startJob } from "../lib/jobs";
import { useOps, OpPanels } from "../lib/ops";
import { getDialogs } from "../components/dialogs/DialogProvider";
import { SegControl } from "../components/ui/SegControl";
import { trackBatchEditorDialog } from "../features/editor";
import { AlbumDetail, ArtistDetail, PlaylistDetail } from "../features/ytm/detail";
import { ytmDownload, type YtmDownloadTarget } from "../features/ytm/download";
import type { YTMAlbum, YTMTrack } from "../features/ytm/types";
import {
  groupAlbums,
  normKey,
  normOne,
  stemOf,
  type AlbumGroup,
  type SortMode,
  type TrackRow,
} from "./library/libUtils";
import { useYtData } from "./library/useYtData";
import { AlbumsTab } from "./library/AlbumsTab";
import { ArtistsTab } from "./library/ArtistsTab";
import { TracksTab } from "./library/TracksTab";
import { PlaylistsTab } from "./library/PlaylistsTab";
import { InboxSection } from "./library/Inbox";
import { LibrarySkeleton } from "./library/LibrarySkeleton";
import { buildArtistLocalCards } from "./library/albumDetail";
import {
  compressPaths,
  deleteTrack,
  editTags,
  metaflowTrack,
  showTrackDetailModal,
  viewLyrics,
  type TrackDetailActions,
} from "./library/trackDetail";

type ViewId = "albums" | "artists" | "tracks" | "playlists";

interface YtOpen {
  kind: "album" | "artist" | "playlist";
  id: string | null;
  name?: string;
  localName?: string;
}

interface Filters {
  artist: string;
  album: string;
  genre: string;
  lyrics: boolean;
  compress: boolean;
  query: string;
}

const EMPTY_FILTERS: Filters = { artist: "", album: "", genre: "", lyrics: false, compress: false, query: "" };

const ICONS = {
  folder:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
  lyrics:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>',
  refresh:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>',
  dots:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>',
};

function readTargetPath(): string {
  const m = location.hash.match(/[?&]path=([^&]*)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export default function LibraryScreen() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<TrackRow[]>([]);
  const [inbox, setInbox] = useState<TrackRow[]>([]);
  const [nameTranslit, setNameTranslit] = useState("auto");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<RenderableMessage>("");
  const [view, setView] = useState<ViewId>("albums");
  const [sort, setSort] = useState<SortMode>("path");
  const [density, setDensity] = useState<string>(() => {
    try {
      const v = localStorage.getItem("music-lib-density") || localStorage.getItem("music-dl-density") || "full";
      return ["full", "compact", "minimal"].includes(v) ? v : "full";
    } catch {
      return "full";
    }
  });
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openAlbumPaths, setOpenAlbumPaths] = useState<string[] | null>(null);
  const [ytOpen, setYtOpen] = useState<YtOpen | null>(null);
  const [detailPath, setDetailPath] = useState("");
  const [countNode, setCountNode] = useState<ReactNode>("");
  const { ops, start: startOp } = useOps();
  const targetPath = useRef(readTargetPath());

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [items, inboxItems, settings] = await Promise.all([
        get<TrackRow[]>("/api/library", { sort }),
        get<TrackRow[]>("/api/library/inbox"),
        get<Record<string, unknown>>("/api/settings"),
      ]);
      setRows(items);
      setInbox(inboxItems);
      setNameTranslit(String(settings?.name_translit || "auto"));
      setLoadError("");
    } catch (e) {
      setLoadError(asRenderableMessage(e));
    }
    setLoading(false);
  }, [sort]);

  useEffect(() => {
    void load();
  }, [load]);

  /* Deep-link ?path=: вкладка «Треки», сброс фильтров, панель деталей.
     Слушаем hashchange — смена query не ремаунтит экран (key по маршруту). */
  useEffect(() => {
    const onHash = () => {
      const p = readTargetPath();
      if (!p) return;
      targetPath.current = p;
      setView("tracks");
      setDetailPath(p);
      setOpenAlbumPaths(null);
      setYtOpen(null);
      setFilters(EMPTY_FILTERS);
    };
    onHash();
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const yt = useYtData(load);

  /* Скачивание из YT-деталей: после — сброс YT-кэша и перечитка библиотеки. */
  const ytDownloadRefresh = useCallback(
    (items: YTMTrack[], target: YtmDownloadTarget) => ytmDownload(items, target, () => yt.refreshAfterYtDownload()),
    [yt],
  );

  /* Смена фильтра/вкладки сбрасывает открытое, как в старом. */
  const switchView = useCallback((v: ViewId) => {
    setView(v);
    setSelected(new Set());
    setOpenAlbumPaths(null);
    setYtOpen(null);
  }, []);

  const toggleSelect = useCallback((path: string) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const matches = useCallback(
    (t: TrackRow) => {
      const f = filters;
      if (f.artist && t.artist !== f.artist) return false;
      if (f.album && t.album !== f.album) return false;
      if (f.genre && t.genre !== f.genre) return false;
      if (f.lyrics && t.has_lyrics) return false;
      if (f.compress && !t.need_compress) return false;
      if (f.query) {
        const q = f.query.toLowerCase();
        const hay = `${t.title || ""} ${t.artist || ""} ${t.album || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    },
    [filters],
  );
  const filtered = useMemo(() => rows.filter(matches), [rows, matches]);

  /* Экшены деталей трека (панель/модалка/Inbox). */
  const detailActions: TrackDetailActions = useMemo(
    () => ({
      editTags: (t) => editTags(t.path, load),
      metaflow: (t) => metaflowTrack(t.path, load),
      viewLyrics: (t) => viewLyrics(t.path, load),
      compress: (paths) => compressPaths(paths, load, startOp),
      deleteTrack: (t) =>
        deleteTrack(t, load, (path) => {
          setDetailPath((cur) => (cur === path ? "" : cur));
        }),
    }),
    [load, startOp],
  );

  /* --- Действия тулбара --- */

  const selectedPaths = useCallback(() => {
    const paths = [...selected];
    if (!paths.length) {
      toast(t("quality.selection.required"), "warn");
      return null;
    }
    return paths;
  }, [selected]);

  const applyMetaToSelected = useCallback(async () => {
    const paths = selectedPaths();
    if (!paths) return;
    const byPath = new Map(rows.map((t) => [t.path, t]));
    const entries = paths.map((p) => ({
      path: p,
      title: byPath.get(p)?.title || stemOf(p),
      artist: byPath.get(p)?.artist || "",
    }));
    const saved = await trackBatchEditorDialog(entries);
    const n = saved ? Object.keys(saved).length : 0;
    if (n) {
      toast(t("library.selection.saved", { count: n }));
      await load();
    }
  }, [selectedPaths, rows, load]);

  const compressSelected = useCallback(async () => {
    const paths = selectedPaths();
    if (!paths) return;
    const ok = await getDialogs().confirm(
      t("library.compress.confirm", { count: paths.length }),
      { defaultOk: false, okTitle: t("library.compress.action") },
    );
    if (!ok) return;
    await compressPaths(paths, load, startOp);
  }, [selectedPaths, load, startOp]);

  const updateLyricsAll = useCallback(async () => {
    const ok = await getDialogs().confirm(
      t("library.lyrics.confirm_all"),
      { okTitle: t("quality.lyrics.update_action") },
    );
    if (!ok) return;
    const op = startOp();
    try {
      op.set(0, t("library.lyrics.preparing"));
      let body: { snapshot?: unknown[] } = {};
      try {
        const d = await get<{ snapshot: unknown[] }>("/api/lyrics/missing");
        body = { snapshot: d.snapshot };
      } catch {
        /* Не блокируем обновление, если снимок кандидатов недоступен. */
      }
      const res = await startJob<{ updated: number; skipped: number; errors: number }>(
        "/api/lyrics/update-all",
        body,
        { onProgress: (d) => op.set(d.percent ?? 0, d.message ?? d.msg) },
      );
      op.set(100, t("library.lyrics.summary", res));
      op.set(100, t("quality.refreshing"));
      await load();
    } catch (e) {
      op.set(0, "");
      toast(asRenderableMessage(e), "error");
    }
  }, [load, startOp]);

  const sortToFolders = useCallback(async () => {
    let plan: { total: number; truncated?: boolean; moves: { from: string; to: string }[] };
    try {
      plan = await post("/api/library/sort/plan", {});
    } catch (e) {
      toast(asRenderableMessage(e), "error");
      return;
    }
    if (!plan.total) {
      toast(t("library.sort.already_sorted"));
      return;
    }
    const ok = await getDialogs().open({
      title: t("library.sort.title"),
      build: () => (
        <>
          <div>{t(plan.truncated ? "library.sort.move_count_truncated" : "library.sort.move_count", { count: plan.total, shown: plan.moves.length })}</div>
          <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            {t("library.sort.explanation")}
          </div>
          <div style={{ maxHeight: 320, overflow: "auto", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-deep)", marginTop: 8 }}>
            {plan.moves.map((m) => (
              <div key={m.from} style={{ padding: "4px 10px", fontSize: 12, display: "flex", gap: 8, alignItems: "baseline" }}>
                <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {m.from.split("/").pop()}
                </span>
                <span className="muted" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
                  {`→ ${m.to.split("/").slice(0, -1).join("/")}`}
                </span>
              </div>
            ))}
          </div>
        </>
      ),
      actions: [
        { title: t("dialogs.cancel"), class: "ghost", value: false, ok: true },
        { title: t("library.sort.action"), value: true, ok: true },
      ],
    });
    if (!ok) return;
    const op = startOp();
    try {
      const res = await startJob<{ moved: number; removed_dirs: number }>(
        "/api/library/sort",
        {},
        { onProgress: (d) => op.set(d.percent ?? 0, d.message ?? d.msg) },
      );
      op.set(100, t("library.sort.summary", { moved: res.moved, removed: res.removed_dirs }));
      await load();
    } catch (e) {
      op.set(0, "");
      toast(asRenderableMessage(e), "error");
    }
  }, [load, startOp]);

  const dedup = useCallback(async () => {
    const mode = await getDialogs().open({
      title: t("library.dedup.mode"),
      build: () => (
        <select style={{ width: "auto" }} aria-label={t("library.dedup.mode")} defaultValue="md5">
          <option value="md5">{t("library.dedup.exact")}</option>
          <option value="semantic">{t("library.dedup.semantic")}</option>
        </select>
      ),
      actions: [
        { title: t("library.dedup.find"), ok: true, value: () => document.querySelector<HTMLSelectElement>(".modal-body select")?.value ?? null },
        { title: t("dialogs.cancel"), class: "ghost", value: null, ok: true },
      ],
    });
    if (mode == null) return;
    const data = await post<{ groups: { files: { path: string; label: string; is_best: boolean }[] }[] }>(
      "/api/library/dedup",
      { mode },
    );
    if (!data.groups.length) {
      toast(t("library.dedup.none"));
      return;
    }
    const checks = new Set<string>();
    data.groups.forEach((g) => g.files.forEach((f) => {
      if (!f.is_best) checks.add(f.path);
    }));
    const paths = await getDialogs().open({
      title: t("quality.category.duplicates"),
      build: () => (
        <>
          <div className="muted" style={{ marginBottom: 8 }}>
            {t("library.dedup.instructions", { count: data.groups.length })}
          </div>
          {data.groups.map((g, gi) => (
            <div key={gi}>
              <div style={{ fontWeight: 600, margin: "8px 0 2px", color: "var(--dim)" }}>{t("library.dedup.group")}</div>
              {g.files.map((f) => (
                <label className="pick-row" key={f.path}>
                  <input
                    type="checkbox"
                    defaultChecked={!f.is_best}
                    onChange={(e) => {
                      if (e.target.checked) checks.add(f.path);
                      else checks.delete(f.path);
                    }}
                  />
                  <span className="pick-label">{f.label}</span>
                  {f.is_best ? <span className="tag ok">{t("library.dedup.best")}</span> : null}
                </label>
              ))}
            </div>
          ))}
        </>
      ),
      actions: [
        { title: t("library.dedup.delete_selected"), ok: true, value: () => [...checks] },
        { title: t("dialogs.close"), class: "ghost", value: null, ok: true },
      ],
    });
    if (!paths || !(paths as string[]).length) return;
    const res = await post<{ deleted: number }>("/api/library/dedup/delete", { paths });
    toast(t("library.dedup.deleted", { count: res.deleted }));
    await load();
  }, [load]);

  const mergeAlbums = useCallback(async () => {
    let data: { groups: { album: string; artists: string[]; files: { path: string }[]; mixed: boolean }[] };
    try {
      data = await post("/api/library/merge-albums/scan", {});
    } catch (e) {
      toast(asRenderableMessage(e), "error");
      return;
    }
    if (!data.groups.length) {
      toast(t("library.merge.none"), "warn");
      return;
    }
    const checked = new Set<string>();
    const picked = await getDialogs().open({
      title: t("library.merge.title"),
      build: () => (
        <>
          <div className="muted" style={{ marginBottom: 8 }}>
            {t("library.merge.instructions", { count: data.groups.length })}
          </div>
          {data.groups.map((g) => (
            <label className="pick-row" style={{ alignItems: "flex-start" }} key={g.album}>
              <input
                type="checkbox"
                defaultChecked
                onChange={(e) => {
                  if (e.target.checked) checked.add(g.album);
                  else checked.delete(g.album);
                }}
              />
              <span style={{ display: "flex", flexDirection: "column" }} onClick={(e) => e.preventDefault()}>
                <span style={{ fontWeight: 600 }}>
                  {g.album}
                  {g.mixed ? <span className="tag warn" style={{ marginInlineStart: 6 }}>{t("library.merge.mixed")}</span> : null}
                </span>
                <span className="muted">{t("library.merge.album_meta", { count: g.files.length, artists: g.artists.length ? g.artists.join(", ") : "—" })}</span>
              </span>
            </label>
          ))}
        </>
      ),
      actions: [
        { title: t("library.merge.selected"), ok: true, value: () => [...checked] },
        { title: t("dialogs.close"), class: "ghost", value: null, ok: true },
      ],
    });
    const selectedGroups = data.groups.filter((g) => (picked as string[] | null)?.includes(g.album));
    if (!selectedGroups.length) return;

    let albumArtist = "";
    if (selectedGroups.some((g) => g.mixed)) {
      const v = await getDialogs().prompt(t("library.merge.album_artist_prompt"), {
        value: "Various Artists",
      });
      if (v == null) return;
      albumArtist = v;
    }
    const payload = selectedGroups.map((g) => ({
      album: g.album,
      album_artist: g.mixed && albumArtist ? albumArtist : g.artists.length === 1 ? g.artists[0] : "",
      paths: g.files.map((f) => f.path),
    }));
    try {
      const res = await post<{ merged: number }>("/api/library/merge-albums/apply", { groups: payload });
      toast(t("library.merge.merged", { count: res.merged }));
      await load();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }, [load]);

  /* Селбар + паддинг вью. */
  useEffect(() => {
    document.body.classList.toggle("sel-open", selected.size > 0);
    return () => document.body.classList.remove("sel-open");
  }, [selected.size]);

  const onCount = useCallback((node: ReactNode) => setCountNode(node), []);
  const openAlbum = useCallback((g: AlbumGroup) => {
    setOpenAlbumPaths(g.paths);
    setDetailPath("");
  }, []);
  const openYtAlbum = useCallback((id: string, name: string) => {
    setYtOpen({ kind: "album", id, name });
  }, []);

  const tabs: [ViewId, string][] = [
    ["albums", t("library.tabs.albums")],
    ["tracks", t("library.tabs.tracks")],
    ["artists", t("library.tabs.artists")],
    ["playlists", t("library.tabs.playlists")],
  ];

  const filterList = filtered; // совпадает с list в старом коде

  let content: ReactNode = null;
  if (ytOpen) {
    const back = () => setYtOpen(null);
    if (ytOpen.kind === "album" && ytOpen.id) {
      content = (
        <AlbumDetail
          id={ytOpen.id}
          title={ytOpen.name}
          back={back}
          onDownload={ytDownloadRefresh}
        />
      );
    } else if (ytOpen.kind === "artist") {
      content = (
        <YtArtistBridge
          o={ytOpen}
          items={rows}
          yt={yt}
          nameTranslit={nameTranslit}
          onBack={back}
          onOpenLocalAlbum={openAlbum}
          onOpenYtAlbum={openYtAlbum}
          onDownload={ytDownloadRefresh}
        />
      );
    } else if (ytOpen.kind === "playlist" && ytOpen.id) {
      content = <PlaylistDetail id={ytOpen.id} back={back} onDownload={ytDownloadRefresh} />;
    }
  } else if (view === "albums") {
    content = (
      <AlbumsTab
        items={rows}
        list={filterList}
        sort={sort}
        density={density}
        nameTranslit={nameTranslit}
        selected={selected}
        toggleSelect={toggleSelect}
        onOpenTrack={(t) => void showTrackDetailModal(t, detailActions)}
        yt={yt}
        openAlbumPaths={openAlbumPaths}
        onOpenAlbum={openAlbum}
        onCloseAlbum={() => setOpenAlbumPaths(null)}
        onOpenYtAlbum={openYtAlbum}
        onCount={onCount}
      />
    );
  } else if (view === "artists") {
    content = (
      <ArtistsTab
        items={rows}
        list={filterList}
        sort={sort}
        density={density}
        nameTranslit={nameTranslit}
        query={filters.query}
        yt={yt}
        onOpenLocalArtist={(name) => setYtOpen({ kind: "artist", id: null, name, localName: name })}
        onOpenYtArtist={(id, name, localName) => setYtOpen({ kind: "artist", id, name, localName })}
        onCount={onCount}
      />
    );
  } else if (view === "tracks") {
    content = (
      <TracksTab
        items={rows}
        list={filterList}
        sort={sort}
        density={density}
        query={filters.query}
        selected={selected}
        toggleSelect={toggleSelect}
        detailPath={detailPath}
        onDetail={setDetailPath}
        yt={yt}
        actions={detailActions}
        onCount={onCount}
      />
    );
  } else {
    content = (
      <PlaylistsTab
        query={filters.query}
        yt={yt}
        onOpenPlaylist={(id) => setYtOpen({ kind: "playlist", id })}
        onCount={onCount}
      />
    );
  }

  return (
    <>
      <h1>{t("nav.library")}</h1>
      <div className="comment">{t("library.subtitle")}</div>

      <>
          <div className="row bar library-toolbar" style={{ marginBottom: 6 }}>
            <div className="seg library-toolbar-tabs library-view-tabs" role="group" aria-label={t("library.views_aria")}>{tabs.map(([v, label]) => <button key={v} type="button" className={clsx(v === view && "active")} aria-pressed={v === view} onClick={() => switchView(v)}>{label}</button>)}</div>
            <SegControl options={[["full", t("library.density.grid")], ["compact", t("library.density.compact")], ["minimal", t("library.density.list")]]} current={density as "full" | "compact" | "minimal"} onChange={(v) => { setDensity(v); try { localStorage.setItem("music-lib-density", v); } catch { /* ignore */ } }} label={t("library.density.aria")} />
            <select title={t("library.sort.control_title")} aria-label={t("library.sort.control_aria")} value={sort} onChange={(e) => setSort(e.target.value as SortMode)} style={{ display: view === "albums" || view === "tracks" ? "" : "none" }}><option value="title">{t("library.sort.by_title")}</option><option value="artist">{t("library.sort.by_artist")}</option><option value="size">{t("library.sort.by_size")}</option></select>
            <button className="ghost iconbtn" type="button" title={t("library.sort.title")} aria-label={t("library.sort.folders_aria")} dangerouslySetInnerHTML={{ __html: ICONS.folder }} onClick={() => void sortToFolders()} /><button className="ghost iconbtn" type="button" title={t("library.lyrics.update_title")} aria-label={t("library.lyrics.update_aria")} dangerouslySetInnerHTML={{ __html: ICONS.lyrics }} onClick={() => void updateLyricsAll()} />
            <OverflowMenu items={[{ label: t("library.selection.tags_action"), fn: () => void applyMetaToSelected() }, { label: t("library.dedup.find_action"), fn: () => void dedup() }, { label: t("library.merge.title"), fn: () => void mergeAlbums() }, { label: t("library.compress.selected_action"), fn: () => void compressSelected() }]} />
            <div className="row lib-right"><span className="muted">{countNode}</span>{selected.size ? <span className="tag ok lib-selbadge">{t("library.selection.badge", { count: selected.size })}</span> : null}<button className="ghost iconbtn" type="button" title={t("quality.refresh")} aria-label={t("library.refresh_aria")} dangerouslySetInnerHTML={{ __html: ICONS.refresh }} onClick={() => void load()} /></div>
          </div>
      </>

      <div className={clsx("selbar", selected.size > 0 && "show")} role="toolbar" aria-label={t("quality.selection.toolbar")}>
        <span className="selbar-count muted">{t("library.selection.count", { count: selected.size })}</span>
        <button type="button" onClick={() => void applyMetaToSelected()}>{t("library.selection.tags")}</button>
        <button className="ghost" type="button" onClick={() => void compressSelected()}>{t("library.compress.action")}</button>
        <button className="ghost" type="button" onClick={() => setSelected(new Set())}>{t("library.selection.deselect_all")}</button>
      </div>

      {loading ? <LibrarySkeleton view={view} density={density} /> : null}
      {loadError ? <div className="panel" style={{ borderColor: "var(--danger)" }}>{resolveMessage(loadError)}</div> : null}
      {!loading && !loadError ? (
        <>
          <OpPanels ops={ops} />
          {inbox.length ? (
            <InboxSection list={inbox} density={density} actions={detailActions} load={load} startProgress={() => startOp()} />
          ) : null}
          <FiltersBar
            items={rows}
            filters={filters}
            setFilters={setFilters}
            full={view === "albums" || view === "tracks"}
            showSelectAll={view === "tracks"}
            selected={selected}
            filtered={filtered}
            toggleSelect={toggleSelect}
          />
          {content}
        </>
      ) : null}
    </>
  );
}

/* Меню «Ещё действия» (•••). */
function OverflowMenu({ items }: { items: { label: string; fn: () => void }[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (ev: MouseEvent) => {
      if (!wrapRef.current?.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("click", away);
    return () => document.removeEventListener("click", away);
  }, [open]);
  return (
    <div className={clsx("overflow-wrap", open && "open")} ref={wrapRef}>
      <button
        className="ghost iconbtn"
        type="button"
        title={t("library.more_actions")}
        aria-label={t("library.more_actions")}
        aria-haspopup="menu"
        aria-expanded={open}
        dangerouslySetInnerHTML={{ __html: ICONS.dots }}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      />
      <div className="overflow-menu" role="menu">
        {items.map((it) => (
          <button
            key={it.label}
            className="ghost"
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              it.fn();
            }}
          >
            {it.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/* Полоса фильтров: поиск с задержкой, селекты, чекбоксы, выбор всех, сброс. */
function FiltersBar({
  items,
  filters,
  setFilters,
  full,
  showSelectAll,
  selected,
  filtered,
  toggleSelect,
}: {
  items: TrackRow[];
  filters: Filters;
  setFilters: (f: Filters) => void;
  full: boolean;
  showSelectAll: boolean;
  selected: Set<string>;
  filtered: TrackRow[];
  toggleSelect: (path: string) => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(filters.query);
  useEffect(() => {
    const t = setTimeout(() => setFilters({ ...filters, query: draft.trim() }), 150);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  const mkSelect = (key: "artist" | "album" | "genre", allLabel: string, getVal: (t: TrackRow) => string, ariaLabel: string) => {
    const seen = new Set<string>();
    items.forEach((t) => {
      const v = getVal(t);
      if (v && !seen.has(v)) seen.add(v);
    });
    return (
      <select
        style={{ width: "auto" }}
        aria-label={ariaLabel}
        value={filters[key]}
        onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}
      >
        <option value="">{allLabel}</option>
        {[...seen].map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>
    );
  };

  const allSelected = filtered.length > 0 && filtered.every((t) => selected.has(t.path));

  return (
    <div className="lib-filters">
          <div style={{ position: "relative", flex: "1 1 180px", minWidth: 140 }}>
            <input
              type="text"
              placeholder={t("library.filters.search_placeholder")}
              aria-label={t("library.filters.search_aria")}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setDraft("");
                  setFilters({ ...filters, query: "" });
                }
              }}
            />
            {draft ? (
              <button
                className="ghost iconbtn"
                type="button"
                title={t("library.filters.clear_search")}
                aria-label={t("library.filters.clear_search")}
                style={{ position: "absolute", insetInlineEnd: 2, top: 2, width: 32, height: 32 }}
                onClick={() => {
                  setDraft("");
                  setFilters({ ...filters, query: "" });
                }}
              >
                ×
              </button>
            ) : null}
          </div>
          <span className="muted" style={{ fontSize: 12 }}>{t("library.filters.label")}</span>
          {full ? (
            <>
              {mkSelect("artist", t("library.filters.all_artists"), (t) => t.artist, t("library.filters.artist_aria"))}
              {mkSelect("album", t("library.filters.all_albums"), (t) => t.album, t("library.filters.album_aria"))}
              {mkSelect("genre", t("library.filters.all_genres"), (t) => t.genre, t("library.filters.genre_aria"))}
              <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="checkbox"
                  checked={filters.lyrics}
                  onChange={(e) => setFilters({ ...filters, lyrics: e.target.checked })}
                />
                {t("library.filters.missing_lyrics")}
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="checkbox"
                  checked={filters.compress}
                  onChange={(e) => setFilters({ ...filters, compress: e.target.checked })}
                />
                {t("library.filters.needs_compression")}
              </label>
            </>
          ) : null}
          {showSelectAll ? (
            <button
              className={clsx("small-btn ghost", allSelected && "active")}
              type="button"
              aria-pressed={allSelected}
              onClick={() => {
                if (allSelected) filtered.forEach((t) => {
                  if (selected.has(t.path)) toggleSelect(t.path);
                });
                else filtered.forEach((t) => {
                  if (!selected.has(t.path)) toggleSelect(t.path);
                });
              }}
            >
               {allSelected ? t("library.selection.deselect_all") : t("quality.selection.select_all", { count: filtered.length })}
            </button>
          ) : null}
          <button
            className="small-btn ghost"
            type="button"
            onClick={() => {
              setDraft("");
              setFilters(EMPTY_FILTERS);
            }}
          >
             {t("library.filters.reset")}
          </button>
    </div>
  );
}

/* Деталь YT-исполнителя с локальными карточками альбомов (дедуп с YT). */
function YtArtistBridge({
  o,
  items,
  yt,
  nameTranslit,
  onBack,
  onOpenLocalAlbum,
  onOpenYtAlbum,
  onDownload,
}: {
  o: YtOpen;
  items: TrackRow[];
  yt: ReturnType<typeof useYtData>;
  nameTranslit: string;
  onBack: () => void;
  onOpenLocalAlbum: (g: AlbumGroup) => void;
  onOpenYtAlbum: (id: string, name: string) => void;
  onDownload: (items: YTMTrack[], target: YtmDownloadTarget) => void;
}) {
  const { i18n } = useTranslation();
  const [cards, setCards] = useState<ReactNode[] | null>(null);
  const [localCount, setLocalCount] = useState(0);
  const [localKeys, setLocalKeys] = useState<Set<string>>(new Set());
  const groupsKey = items.map((t) => t.path).join("|");
  const locale = i18n.resolvedLanguage || i18n.language;

  useEffect(() => {
    let alive = true;
    const localName = o.localName || o.name || "";
    const groups = groupAlbums(items.filter((t) => normOne(t.artist) === normOne(localName)), locale);
    setLocalKeys(new Set(groups.map((g) => normKey(g.title, g.artist))));
    setLocalCount(groups.reduce((n, g) => n + g.tracks.length, 0));
    setCards(null);
    (async () => {
      const saved = await yt.ytData<YTMAlbum>("albums");
      if (!alive) return;
      const ymap = new Map(saved.map((ya) => [normKey(ya.title, ya.artist), ya]));
      const twins = new Map<string, YTMAlbum | null>();
      await Promise.all(
        groups.map(async (g) => {
          const ya = ymap.get(normKey(g.title, g.artist)) || (await yt.findAlbumTwin(g));
          twins.set(g.key, ya ?? null);
        }),
      );
      if (!alive) return;
      setCards(
        buildArtistLocalCards(groups, twins, nameTranslit, (g) => {
          onOpenLocalAlbum(g);
          onBack();
        }),
      );
    })();
    return () => {
      alive = false;
    };
  }, [groupsKey, locale, o.id, o.localName, yt.epoch]);

  return (
    <ArtistDetail
      id={o.id || ""}
      name={o.name}
      back={onBack}
      onDownload={onDownload}
      localCards={cards ?? []}
      localCount={localCount}
      ytAlbumFiltered={(al) => localKeys.has(normKey(al.title, al.artist))}
      onOpenAlbum={onOpenYtAlbum}
    />
  );
}
