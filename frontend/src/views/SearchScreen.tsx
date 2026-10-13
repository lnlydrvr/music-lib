/* Поиск и скачивание: YouTube / YouTube Music, прямые ссылки, плейлисты.
   Скачивание — job'ы (прогресс в доке загрузок), метафлоу — runMetaflow
   (LRCLIB уже внутри). Локальные прогресс-панели — useOps. */
import { useEffect, useRef, useState, type ReactNode } from "react";
import clsx from "clsx";
import { Virtuoso } from "react-virtuoso";
import { get, post } from "../lib/api";
import { toast } from "../lib/toast";
import { startJob } from "../lib/jobs";
import { useOps, OpPanels, type OpHandle } from "../lib/ops";
import { fmtDuration } from "../lib/format";
import { useDialogs } from "../components/dialogs/DialogProvider";
import { PreviewButton } from "../components/PreviewButton";
import { SegControl } from "../components/ui/SegControl";
import { Spinner } from "../components/ui/Spinner";
import { SkeletonRows } from "../components/ui/SkeletonRows";
import { EmptyState } from "../components/ui/EmptyState";
import { Table } from "../components/ui/Table";
import { TrackRow } from "../components/ui/TrackRow";
import { metaflowStageMessage, runMetaflow } from "../features/editor";
import type { YTMTrack } from "../features/ytm";
import { ytmDownload, type YtmDownloadTarget } from "../features/ytm/download";
import { RadioPanel } from "../features/ytm/detail";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../i18n/messages";
import { useTranslation } from "react-i18next";
import type { PipeStage } from "../components/ui/Pipeline";

type EngineId = "ytmusic" | "youtube";

interface YtResult {
  id: string;
  title: string;
  uploader: string;
  duration: number;
  url: string;
  thumbnail: string;
}

type Item = { kind: "yt"; r: YtResult } | { kind: "ytm"; r: YTMTrack };

interface PlaylistEntry {
  index: number;
  id: string;
  title: string;
  uploader: string;
  duration: number;
  url: string;
}


/* Порог виртуализации: короткие списки — простой map (и в jsdom без
   ResizeObserver), длинные — Virtuoso по window scroll. */
const VIRTUAL_THRESHOLD = 30;
/* .trackrow (48 обложка + 2×8 padding + 2 бордер = 66) + 8 отступ —
   интервал живёт в .vrow, margin строки обнулён (styles.css). */
const ROW_HEIGHT = 74;
const TRACK_STAGES: PipeStage[] = [
  { id: "download", label: { code: "ytm.download.title" } }, { id: "meta", label: { code: "editor.source" } },
  { id: "lyrics", label: { code: "quality.lyrics.singular" } }, { id: "move", label: { code: "recommend.apply.library" } },
];
const BATCH_STAGES: PipeStage[] = [{ id: "download", label: { code: "ytm.download.title" } }, { id: "move", label: { code: "recommend.apply.library" } }];

export default function SearchScreen() {
  const { t } = useTranslation();
  const dialogs = useDialogs();
  const [engine, setEngine] = useState<EngineId>("youtube");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  /* results: heading + список; playlist — отдельно (своя вёрстка). */
  const [results, setResults] = useState<{ query: string; engine: EngineId; items: Item[] } | null>(null);
  const [playlist, setPlaylist] = useState<{ url: string; entries: PlaylistEntry[] } | null>(null);
  const [searchError, setSearchError] = useState<{ q: string; msg: RenderableMessage } | null>(null);
  const [loading, setLoading] = useState(false);
  const [canMore, setCanMore] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [arrows, setArrows] = useState<string[]>([]);
  const [radioSeed, setRadioSeed] = useState<YTMTrack | null>(null);
  const { ops, start: startOp } = useOps();
  const searchLimit = useRef(10);
  const lastQuery = useRef("");
  const lastEngine = useRef<EngineId>("youtube");

  /* Источник поиска из настроек: YouTube Music по умолчанию, без подключения — YouTube. */
  useEffect(() => {
    get<Record<string, unknown>>("/api/settings")
      .then((s) => {
        if (s.search_source !== "youtube" && s.ytmusic_connected !== false) setEngine("ytmusic");
      })
      .catch(() => {
        /* дефолт — youtube */
      });
  }, []);

  const markYtmInLibrary = (videoId: string) => {
    setResults((res) =>
      res
        ? {
            ...res,
            items: res.items.map((it) =>
              it.kind === "ytm" && it.r.video_id === videoId ? { kind: "ytm", r: { ...it.r, in_library: true } } : it,
            ),
          }
        : res,
    );
  };

  /* Метафлоу поверх скачанного: шаги LRCLIB идут внутри runMetaflow —
     по onStep двигаем пайплайн. */
  async function metaflowStage(op: OpHandle, filepath: string, thumb: string) {
    op.go("meta", "active");
    op.set(80, { code: "search.metaflow.metadata_searching" });
    const ok = await dialogs.confirm(t("search.metaflow.confirm"), { defaultOk: true, okTitle: t("dialogs.yes"), cancelTitle: t("search.metaflow.skip") });
    if (ok) {
      await runMetaflow(filepath, thumb, (step) => {
        op.set(85, metaflowStageMessage(step));
        if (step === "lyrics") {
          op.go("meta", "done");
          op.go("lyrics", "active");
        }
      });
    } else {
      op.go("meta", "done");
      op.go("lyrics", "active");
      op.set(90, { code: "search.metaflow.lyrics_updating" });
    }
    op.go("lyrics", "done");
  }

  /* Скачивание YTM-результата: теги из YouTube Music, архив .m3u8, перенос —
     затем интерактивный metaflow по уже лежащему в библиотеке файлу. */
  async function ytmDownloadSingle(r: YTMTrack) {
    const target = {
      kind: "track",
      providerId: r.video_id,
      title: { code: "jobs.ytm.name" },
    } satisfies YtmDownloadTarget;
    const op = startOp(TRACK_STAGES);
    op.go("download", "active");
    try {
      const res = await ytmDownload(
        [{
          video_id: r.video_id,
          title: r.title,
          artist: r.artist,
          album: r.album,
          year: r.year,
          track_number: r.track_number,
          video_type: r.video_type,
          cover_url: r.cover_url,
          album_artist: r.artist,
        }],
        target,
        undefined,
        (d) => { if (d.percent != null) op.set(d.percent, d.message ?? d.msg); },
      );
      if (!res) return;
      const item = (res.items || [])[0] || {};
      if (item.error || !item.ok) {
        const error: RenderableMessage = item.error || { code: "jobs.download.failed" };
        op.go("download", "error");
        toast(error, "error");
        return;
      }
      op.go("download", "done");
      op.go("move", "done");
      const completion: RenderableMessage = res.archive
        ? { code: "ytm.download.archive", params: { name: res.archive.split("/").pop() || res.archive } }
        : { code: "ytm.download.completed", params: { count: res.ok } };
      op.set(100, completion);
      toast(completion);
      if (item.path) await metaflowStage(op, item.path, r.cover_url || "");
      markYtmInLibrary(r.video_id);
    } catch (e) {
      op.go("download", "error");
      toast(asRenderableMessage(e), "error");
    }
  }

  /* Перенос в библиотеку после метафлоу (YouTube-флоу, move:false в job). */
  async function postDownload(op: OpHandle, filepath: string, thumb: string) {
    let cur = "meta";
    try {
      await metaflowStage(op, filepath, thumb);
      cur = "move";
      op.go("move", "active");
      op.set(95, { code: "search.metaflow.moving" });
      const mv = await post<{ to: string }>("/api/library/move", { path: filepath });
      op.go("move", "done");
      op.set(100, { code: "search.metaflow.moved", params: { path: mv.to } });
      setArrows((arr) => [`→ ${mv.to}`, ...arr]);
      toast({ code: "search.metaflow.added_to_library" });
    } catch (e) {
      op.go(cur, "error");
      op.set(0, "");
      toast(asRenderableMessage(e), "error");
    }
  }

  async function downloadSingle(url: string, thumb: string, title = "") {
    const op = startOp(TRACK_STAGES);
    op.go("download", "active");
    try {
      const res = await startJob<{ filepath: string; info?: { thumbnail?: string } }>(
        "/api/download",
        { url, move: false },
        { onProgress: (d) => { if (d.percent != null) op.set(d.percent, d.message ?? d.msg); }, title: title || url },
      );
      op.set(100, { code: "search.metaflow.downloaded_processing" });
      op.go("download", "done");
      await postDownload(op, res.filepath, res.info?.thumbnail || thumb);
    } catch (e) {
      op.go("download", "error");
      toast(asRenderableMessage(e), "error");
    }
  }

  async function downloadDirect(url: string) {
    setResults(null);
    setPlaylist(null);
    const op = startOp(TRACK_STAGES);
    op.go("download", "active");
    try {
      const res = await startJob<{ filepath: string; info?: { thumbnail?: string } }>(
        "/api/download",
        { url, move: false },
        { onProgress: (d) => { if (d.percent != null) op.set(d.percent, d.message ?? d.msg); }, title: url },
      );
      op.set(100, { code: "search.metaflow.downloaded_processing" });
      op.go("download", "done");
      await postDownload(op, res.filepath, res.info?.thumbnail || "");
    } catch (e) {
      op.go("download", "error");
      op.set(0, "");
      toast(asRenderableMessage(e), "error");
    }
  }

  async function batchDownload(urls: string[]) {
    if (!urls.length) return;
    const op = startOp(BATCH_STAGES);
    op.go("download", "active");
    try {
      const res = await startJob<{ ok: number; items: unknown[] }>(
        "/api/download/batch",
        { urls, move: true },
        { onProgress: (d) => { if (d.percent != null) op.set(d.percent, d.message ?? d.msg); }, title: { code: "search.batch.title", params: { count: urls.length } } },
      );
      op.go("move", "done");
      const completion: RenderableMessage = { code: "search.batch.completed", params: { downloaded: res.ok, failed: res.items.length - res.ok } };
      op.set(100, completion);
      toast(completion);
    } catch (e) {
      op.go("download", "error");
      toast(asRenderableMessage(e), "error");
    }
  }

  async function doSearch(raw: string, append: boolean, eng: EngineId) {
    lastQuery.current = raw;
    lastEngine.current = eng;
    if (!append) {
      searchLimit.current = 10;
      setResults(null);
      setPlaylist(null);
      setSearchError(null);
      setLoading(true);
      setBusy(true);
    }
    try {
      if (eng === "ytmusic") {
        const res = await get<{ tracks: YTMTrack[] }>("/api/ytmusic/search", { q: raw, limit: searchLimit.current });
        const fresh = (res.tracks || []).map((t): Item => ({ kind: "ytm", r: t }));
        applyItems(append, fresh, raw, eng);
        return;
      }
      const res = await get<YtResult[]>("/api/search", { q: raw, limit: searchLimit.current });
      applyItems(append, res.map((r): Item => ({ kind: "yt", r })), raw, eng);
    } catch (e) {
      if (!append) {
        setLoading(false);
        setBusy(false);
        setSearchError({ q: raw, msg: asRenderableMessage(e) });
      } else {
        toast(asRenderableMessage(e), "error");
      }
    }
  }

  /* Догрузка «Показать ещё»: сервер не пагинирует — берём только хвост ответа
     (в старом коде полный ответ конкатенировался и первые результаты дублировались). */
  function applyItems(append: boolean, fresh: Item[], query: string, resultEngine: EngineId) {
    setBusy(false);
    setLoading(false);
    setSearchError(null);
    if (!append) {
      setResults({ query, engine: resultEngine, items: fresh });
      setCanMore(fresh.length >= searchLimit.current);
      return;
    }
    setResults((res) => {
      if (!res) return { query, engine: resultEngine, items: fresh };
      const tail = fresh.slice(res.items.length);
      setCanMore(!!tail.length && fresh.length >= searchLimit.current);
      return { ...res, items: [...res.items, ...tail] };
    });
  }

  async function loadPlaylist(url: string) {
    setLoading(true);
    setBusy(true);
    setResults(null);
    setSearchError(null);
    try {
      const entries = await get<PlaylistEntry[]>("/api/playlist", { url });
      setPlaylist({ url, entries });
      setChecked(new Set());
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
    setLoading(false);
    setBusy(false);
  }

  function run(raw: string) {
    if (!raw) return;
    setRadioSeed(null);
    if (/^https?:\/\//.test(raw)) {
      /* URL-загрузка тоже меняет lastQuery: ветка рендера показывает
         «Обработка...», а не скелетон строк поиска. */
      lastQuery.current = raw;
      if (/[?&]list=|\/playlist\b|playlist[?=]/.test(raw)) loadPlaylist(raw);
      else downloadDirect(raw);
      return;
    }
    doSearch(raw, false, engine);
  }

  const more = () => {
    searchLimit.current += 10;
    doSearch(lastQuery.current, true, lastEngine.current);
  };

  const renderResult = (it: Item, i: number): ReactNode =>
    it.kind === "yt" ? (
      <TrackRow
        key={it.r.id || i}
        coverSrc={it.r.thumbnail || ""}
        title={it.r.title || t("common.empty_value")}
        sub={it.r.uploader || ""}
        meta={fmtDuration(it.r.duration)}
        actions={
          <>
            <PreviewButton url={it.r.url} title={it.r.title} artist={it.r.uploader} coverUrl={it.r.thumbnail} />
            <button
              className="small-btn"
              type="button"
              aria-label={t("search.download_aria", { title: it.r.title || it.r.url })}
              onClick={() => downloadSingle(it.r.url, it.r.thumbnail, it.r.title)}
            >
              {t("search.download")}
            </button>
          </>
        }
      />
    ) : (
      <TrackRow
        key={it.r.video_id || i}
        coverSrc={it.r.cover_url || ""}
        title={it.r.title || t("common.empty_value")}
        sub={it.r.artist || ""}
        meta={fmtDuration(it.r.duration)}
        actions={
          <>
            <PreviewButton
              url={`https://www.youtube.com/watch?v=${it.r.video_id}`}
              title={it.r.title}
              artist={it.r.artist}
              coverUrl={it.r.cover_url}
            />
            {it.r.in_library ? (
              <span className="tag" style={{ opacity: ".8" }}>{t("search.in_library")}</span>
            ) : (
              <button
                className="small-btn"
                type="button"
                aria-label={t("search.download_aria", { title: it.r.title || it.r.video_id })}
                onClick={() => void ytmDownloadSingle(it.r)}
              >
                {t("search.download")}
              </button>
            )}
          </>
        }
      />
    );

  return (
    <div>
      <h1>{t("search.title")}</h1>
      <div className="comment">{t("search.subtitle")}</div>
      <SegControl
        options={[
          ["ytmusic", "YouTube Music"],
          ["youtube", "YouTube"],
        ]}
        current={engine}
        onChange={setEngine}
        label={t("search.source")}
      />
      <label className="visually-hidden" htmlFor="search-query">{t("search.query")}</label>
      <div className="row" style={{ marginTop: 8 }}>
        <div className="grow">
          <input
            type="text"
            id="search-query"
            placeholder={t("search.placeholder")}
            aria-label={t("search.query")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") run(q.trim());
            }}
          />
        </div>
        <button type="button" className={clsx(busy && "is-loading")} disabled={busy} onClick={() => run(q.trim())}>
          {busy ? t("search.searching") : t("search.action")}
        </button>
      </div>

      <div style={{ marginTop: 16 }}>
        <OpPanels ops={ops} />
        {arrows.map((a, i) => (
          <div key={i} className="muted" style={{ fontSize: 12 }}>{a}</div>
        ))}
        {radioSeed ? <RadioPanel seed={radioSeed} onClose={() => setRadioSeed(null)} /> : null}
        {/* Новый поиск: строки-заглушки той же формы, что результаты
            (TrackRow) — вместо текстовой строки до ответа; URL-обработка
            (плейлист) остаётся на текстовой загрузке: финал — таблица. */}
        {loading ? (
          /https?:/.test(lastQuery.current) ? (
            <Spinner text={t("search.processing")} />
          ) : (
            <SkeletonRows n={6} meta />
          )
        ) : null}

        {searchError ? (
          <div className="panel" style={{ borderColor: "var(--danger)" }}>
            <div>{t("search.failed", { message: resolveMessage(searchError.msg) })}</div>
            <button className="small-btn ghost" style={{ marginTop: 8 }} type="button" onClick={() => run(searchError.q)}>
              {t("search.retry")}
            </button>
          </div>
        ) : null}

        {playlist ? (
          <>
            <h2>{t("search.playlist", { count: playlist.entries.length })}</h2>
            <Table
              headers={["", "", "", "#", t("editor.fields.title"), t("search.channel"), t("search.duration")]}
            >
              {playlist.entries.map((e) => (
                <tr key={e.url}>
                  <td>
                    <input
                      type="checkbox"
                       aria-label={t("search.select", { title: e.title || e.url })}
                      checked={checked.has(e.url)}
                      onChange={() =>
                        setChecked((s) => {
                          const next = new Set(s);
                          if (next.has(e.url)) next.delete(e.url);
                          else next.add(e.url);
                          return next;
                        })
                      }
                    />
                  </td>
                  <td>
                    <button className="small-btn" type="button" onClick={() => downloadSingle(e.url, "")}>
                      {t("search.download")}
                    </button>
                  </td>
                  <td>
                    <PreviewButton url={e.url} title={e.title} artist={e.uploader} />
                  </td>
                  <td className="muted">{e.index}</td>
                  <td>
                    <b>{e.title}</b>
                  </td>
                  <td className="muted">{e.uploader}</td>
                  <td className="muted">{fmtDuration(e.duration)}</td>
                </tr>
              ))}
            </Table>
            <div className="row" style={{ marginTop: 10 }}>
              <button className="small-btn ghost" type="button" onClick={() => setChecked(new Set(playlist.entries.map((e) => e.url)))}>
                {t("search.all")}
              </button>
              <button className="small-btn ghost" type="button" onClick={() => setChecked(new Set())}>
                {t("search.none")}
              </button>
              <button type="button" disabled={checked.size === 0} onClick={() => batchDownload([...checked])}>
                {t("search.download_selected", { count: checked.size })}
              </button>
            </div>
          </>
        ) : null}

        {results ? (
          <>
            <h2>{t(results.engine === "ytmusic" ? "search.results_ytm" : "search.results_yt", { query: results.query })}</h2>
            {results.items.length ? (
              <>
                {results.items.length > VIRTUAL_THRESHOLD ? (
                  <Virtuoso
                    useWindowScroll
                    fixedItemHeight={ROW_HEIGHT}
                    increaseViewportBy={{ top: 600, bottom: 600 }}
                    data={results.items}
                    itemContent={(i, it) => <div className="vrow">{renderResult(it, i)}</div>}
                  />
                ) : (
                  results.items.map((it, i) => renderResult(it, i))
                )}
                {canMore ? (
                  <button className="small-btn ghost" style={{ marginTop: 10 }} type="button" onClick={more}>
                    {t("search.more", { count: results.items.length })}
                  </button>
                ) : null}
                <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>{t(results.engine === "ytmusic" ? "search.ytm_note" : "search.yt_note")}</div>
              </>
            ) : (
              <EmptyState art="∅" title={t("search.empty")} sub={t("search.empty_hint")} />
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
