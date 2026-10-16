import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { get } from "../lib/api";
import { startJob } from "../lib/jobs";
import { useOps, OpPanels } from "../lib/ops";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../i18n/messages";
import { toast } from "../lib/toast";
import { SegControl } from "../components/ui/SegControl";
import { TrackRow } from "../components/ui/TrackRow";
import { EmptyState } from "../components/ui/EmptyState";
import { fmtDuration } from "../lib/format";

type LucidaService = "qobuz" | "amazon";
type LucidaKind = "album" | "track";

interface LucidaStatus {
  available: boolean;
  access_ready: boolean;
  chromium_ready: boolean;
  service: LucidaService;
}

interface LucidaItem {
  url: string;
  title?: string;
  artist?: string;
  album?: string;
  cover_url?: string;
}

interface LucidaReleaseTrack { number: number; title: string; duration?: string | number; }
interface LucidaRelease { title: string; artist: string; tracks: LucidaReleaseTrack[]; track_count: number; }

interface LucidaResults {
  albums: LucidaItem[];
  tracks: LucidaItem[];
  service: LucidaService;
}

type LucidaDownloadOutcome = "complete" | "failed" | "partial";

const SERVICES: [LucidaService, string][] = [["qobuz", "Qobuz"], ["amazon", "Amazon Music"]];

function validService(value: unknown): LucidaService {
  return value === "amazon" ? "amazon" : "qobuz";
}

function validItems(value: unknown): LucidaItem[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const candidate = item as Partial<LucidaItem>;
    if (typeof candidate.url !== "string" || !candidate.url.trim()) return [];
    return [{ ...candidate, url: candidate.url.trim() } as LucidaItem];
  });
}

function isLucidaStatus(value: unknown): value is LucidaStatus {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Partial<LucidaStatus>;
  return (candidate.service === "qobuz" || candidate.service === "amazon")
    && typeof candidate.available === "boolean"
    && typeof candidate.access_ready === "boolean"
    && typeof candidate.chromium_ready === "boolean";
}

function isAbortError(error: unknown): boolean {
  return Boolean(error && typeof error === "object" && "name" in error && error.name === "AbortError");
}

function validRelease(value: unknown): LucidaRelease | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const candidate = value as Partial<LucidaRelease>;
  if (typeof candidate.title !== "string" || typeof candidate.artist !== "string" || !Array.isArray(candidate.tracks)) return null;
  const tracks = candidate.tracks.flatMap((track) => {
    if (!track || typeof track !== "object" || typeof track.number !== "number" || typeof track.title !== "string") return [];
    const duration = typeof track.duration === "string"
      ? track.duration
      : typeof track.duration === "number" && Number.isFinite(track.duration) && track.duration >= 0
        ? track.duration
        : undefined;
    return [{ number: track.number, title: track.title, ...(duration !== undefined ? { duration } : {}) }];
  });
  return { title: candidate.title, artist: candidate.artist, tracks, track_count: typeof candidate.track_count === "number" ? candidate.track_count : tracks.length };
}

/** The completed Job result is sanitized by the API; do not expose its fields. */
function downloadOutcome(result: unknown): LucidaDownloadOutcome {
  if (!result || typeof result !== "object" || Array.isArray(result)) return "complete";
  const response = result as { error?: unknown; items?: unknown };
  if (response.error) return "failed";
  if (Array.isArray(response.items) && response.items.some((item) => (
    Boolean(
      item && typeof item === "object" && !Array.isArray(item)
       && ((item as { status?: unknown }).status === "fail" || (item as { error?: unknown }).error || (item as { message?: unknown }).message),
    )
  ))) return "partial";
  return "complete";
}

export default function LucidaScreen() {
  const { t } = useTranslation();
  const [service, setService] = useState<LucidaService>("qobuz");
  const [status, setStatus] = useState<LucidaStatus | null>(null);
  const [statusError, setStatusError] = useState<RenderableMessage>("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<LucidaResults | null>(null);
  const [searchError, setSearchError] = useState<RenderableMessage>("");
  const [searching, setSearching] = useState(false);
  const [setupPending, setSetupPending] = useState(false);
  const [pendingDownloads, setPendingDownloads] = useState<Set<string>>(() => new Set());
  const [expandedAlbums, setExpandedAlbums] = useState<Set<string>>(() => new Set());
  const [releases, setReleases] = useState<Record<string, LucidaRelease | null>>({});
  const [releaseLoading, setReleaseLoading] = useState<Set<string>>(() => new Set());
  const [releaseErrors, setReleaseErrors] = useState<Set<string>>(() => new Set());
  const searchSequence = useRef(0);
  const searchController = useRef<AbortController | null>(null);
  const statusSequence = useRef(0);
  const setupPendingRef = useRef(false);
  const pendingDownloadsRef = useRef(new Set<string>());
  const serviceRef = useRef(service);
  const userSelectedService = useRef(false);
  const serviceSelectionGeneration = useRef(0);
  const lifecycleGeneration = useRef(0);
  const { ops, start: startOp } = useOps();

  const isActive = useCallback((generation: number, signal?: AbortSignal) => (
    lifecycleGeneration.current === generation && !signal?.aborted
  ), []);

  const selectService = useCallback((selectedService: LucidaService, isUserSelection = true) => {
    if (isUserSelection) {
      userSelectedService.current = true;
      serviceSelectionGeneration.current += 1;
    }
    if (selectedService === serviceRef.current) return;
    searchController.current?.abort();
    searchController.current = null;
    searchSequence.current += 1;
    statusSequence.current += 1;
    serviceRef.current = selectedService;
    setService(selectedService);
    setResults(null);
    setSearchError("");
    setSearching(false);
  }, []);

  const loadStatus = useCallback(async (selectedService: LucidaService, signal?: AbortSignal, generation = lifecycleGeneration.current) => {
    if (!isActive(generation, signal) || selectedService !== serviceRef.current) return;
    const requestId = ++statusSequence.current;
    setStatus(null);
    setStatusError("");
    try {
      const next = await get<unknown>("/api/lucida/status", { service: selectedService }, "GET", { signal });
      if (isActive(generation, signal) && requestId === statusSequence.current && selectedService === serviceRef.current) {
        if (isLucidaStatus(next)) setStatus(next);
        else setStatusError({ code: "api.errors.lucida_failed" });
      }
    } catch (error) {
      if (!isAbortError(error) && isActive(generation, signal) && requestId === statusSequence.current && selectedService === serviceRef.current) setStatusError(asRenderableMessage(error));
    }
  }, [isActive]);

  useEffect(() => {
    const generation = ++lifecycleGeneration.current;
    return () => {
      if (lifecycleGeneration.current === generation) lifecycleGeneration.current += 1;
      searchController.current?.abort();
      searchController.current = null;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const selectionGeneration = serviceSelectionGeneration.current;
    get<{ lucida_service?: unknown }>("/api/settings", undefined, "GET", { signal: controller.signal })
      .then((settings) => {
        if (!controller.signal.aborted && !userSelectedService.current && selectionGeneration === serviceSelectionGeneration.current) {
          selectService(validService(settings.lucida_service), false);
        }
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [selectService]);

  useEffect(() => {
    const controller = new AbortController();
    void loadStatus(service, controller.signal, lifecycleGeneration.current);
    return () => controller.abort();
  }, [loadStatus, service]);

  const unavailable = status !== null && !status.available;
  const accessMissing = status !== null && status.available && !status.access_ready;
  const chromiumMissing = status !== null && status.available && !status.chromium_ready;
  const ready = status?.available === true && status.access_ready === true && status.chromium_ready === true;
  const canPrepareAccess = status?.available === true
    && status.chromium_ready === true
    && status.access_ready === false
    && !statusError
    && !setupPending;

  async function prepareAccess() {
    const generation = lifecycleGeneration.current;
    if (setupPendingRef.current) return;
    setupPendingRef.current = true;
    setSetupPending(true);
    const op = startOp();
    op.set(0, { code: "lucida.setup_progress" });
    try {
      await startJob("/api/lucida/setup", {}, {
        title: { code: "jobs.lucida.setup_name" },
        onProgress: (event) => {
          if (isActive(generation)) op.set(event.percent ?? 0, event.message ?? event.msg);
        },
      });
      if (!isActive(generation)) return;
      op.set(100, { code: "lucida.setup_complete" });
      await loadStatus(serviceRef.current, undefined, generation);
    } catch (error) {
      if (!isActive(generation) || isAbortError(error)) return;
      op.set(0, asRenderableMessage(error));
      toast(asRenderableMessage(error), "error");
    } finally {
      setupPendingRef.current = false;
      if (isActive(generation)) setSetupPending(false);
    }
  }

  async function search() {
    const trimmed = query.trim();
    if (!trimmed || !ready) return;
    const searchService = service;
    const requestId = ++searchSequence.current;
    const generation = lifecycleGeneration.current;
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    const isCurrentSearch = () => (
      isActive(generation, controller.signal)
      && searchController.current === controller
      && requestId === searchSequence.current
      && searchService === serviceRef.current
    );
    setSearching(true);
    setResults(null);
    setSearchError("");
    try {
      const found = await get<{ albums?: unknown; tracks?: unknown }>("/api/lucida/search", { q: trimmed, service: searchService }, "GET", { signal: controller.signal });
      if (isCurrentSearch()) {
        setResults({ albums: validItems(found.albums), tracks: validItems(found.tracks), service: searchService });
      }
    } catch (error) {
      if (!isAbortError(error) && isCurrentSearch()) setSearchError(asRenderableMessage(error));
    } finally {
      if (isCurrentSearch()) setSearching(false);
      if (searchController.current === controller) searchController.current = null;
    }
  }

  async function download(item: LucidaItem, kind: LucidaKind, resultService: LucidaService) {
    const generation = lifecycleGeneration.current;
    const key = `${resultService}:${kind}:${item.url}`;
    if (pendingDownloadsRef.current.has(key)) return;
    pendingDownloadsRef.current.add(key);
    setPendingDownloads((current) => new Set(current).add(key));
    const op = startOp();
    op.set(0, { code: "lucida.download_progress" });
    try {
      const result = await startJob<unknown>("/api/lucida/download", { url: item.url, kind, service: resultService }, {
        title: { code: "jobs.lucida.download_name" },
        onProgress: (event) => {
          if (!isActive(generation)) return;
          const progressMessage = typeof event.done === "number" && typeof event.total === "number"
            ? { code: "lucida.download_progress_tracks", params: { done: event.done, total: event.total, percent: event.percent ?? 0 } } as const
            : event.message ?? event.msg;
          op.set(event.percent ?? 0, progressMessage);
        },
      });
      if (!isActive(generation)) return;
      const outcome = downloadOutcome(result);
      if (outcome === "failed") {
        op.set(0, { code: "lucida.download_failed" });
        toast({ code: "lucida.download_failed" }, "error");
      } else if (outcome === "partial") {
        op.set(100, { code: "lucida.download_partial" });
        toast({ code: "lucida.download_partial" }, "warn");
      } else {
        op.set(100, { code: "lucida.download_complete" });
        toast({ code: "lucida.download_complete" });
      }
    } catch (error) {
      if (!isActive(generation)) return;
      op.set(0, asRenderableMessage(error));
      toast(asRenderableMessage(error), "error");
    } finally {
      pendingDownloadsRef.current.delete(key);
      if (isActive(generation)) {
        setPendingDownloads((current) => {
          const next = new Set(current);
          next.delete(key);
          return next;
        });
      }
    }
  }

  async function toggleRelease(item: LucidaItem, resultService: LucidaService, retry = false) {
    const key = item.url;
    if (expandedAlbums.has(key) && !retry) {
      setExpandedAlbums((current) => { const next = new Set(current); next.delete(key); return next; });
      return;
    }
    setExpandedAlbums((current) => new Set(current).add(key));
    if (Object.prototype.hasOwnProperty.call(releases, key)) return;
    setReleaseLoading((current) => new Set(current).add(key));
    setReleaseErrors((current) => { const next = new Set(current); next.delete(key); return next; });
    try {
      const release = validRelease(await get<unknown>("/api/lucida/release", { url: key, service: resultService }));
      if (release) setReleases((current) => ({ ...current, [key]: release }));
      else setReleaseErrors((current) => new Set(current).add(key));
    } catch {
      setReleaseErrors((current) => new Set(current).add(key));
    } finally {
      setReleaseLoading((current) => { const next = new Set(current); next.delete(key); return next; });
    }
  }

  function renderItem(item: LucidaItem, kind: LucidaKind, resultService: LucidaService, index: number) {
    const title = item.title || item.url;
    const sub = kind === "track" ? [item.artist, item.album].filter(Boolean).join(" · ") : item.artist || "";
    const downloading = pendingDownloads.has(`${resultService}:${kind}:${item.url}`);
    const expanded = kind === "album" && expandedAlbums.has(item.url);
    const tracklistId = `lucida-tracklist-${kind}-${index}`;
    const release = releases[item.url];
    return (
      <div key={`${kind}:${item.url}`}>
        <TrackRow
          coverSrc={item.cover_url}
          coverAltTitle={t("common.cover_alt", { title })}
          title={title}
          sub={sub}
          actions={
            <>
              {kind === "album" ? <button
                className={clsx("lucida-disclosure", expanded && "is-expanded")}
                type="button"
                aria-expanded={expanded}
                aria-controls={tracklistId}
                aria-label={t(expanded ? "lucida.hide_tracklist" : "lucida.show_tracklist", { title })}
                onClick={() => void toggleRelease(item, resultService)}
              >
                <span aria-hidden="true" />
              </button> : null}
              <button className={clsx("small-btn lucida-download", downloading && "is-loading")} type="button" aria-label={t("lucida.download_aria", { title })} disabled={downloading} onClick={() => void download(item, kind, resultService)}>
                {t("search.download")}
              </button>
            </>
          }
        />
        {kind === "album" && expanded ? <div id={tracklistId} className="lucida-tracklist" role="region" aria-label={t("lucida.tracklist_aria", { title })}>
          {releaseLoading.has(item.url) ? <div className="muted">{t("lucida.tracklist_loading")}</div>
            : releaseErrors.has(item.url) ? <div className="lucida-tracklist-error">{t("lucida.tracklist_error")} <button className="small-btn ghost" type="button" aria-label={t("lucida.retry_tracklist", { title })} onClick={() => void toggleRelease(item, resultService, true)}>{t("search.retry")}</button></div>
              : release?.tracks.length ? release.tracks.map((track) => {
                const duration = typeof track.duration === "number" ? fmtDuration(track.duration) : track.duration;
                return <div className="lucida-track" key={`${track.number}-${track.title}`}><span className="lucida-track-number">{track.number}</span><span>{track.title}</span>{duration ? <span className="lucida-track-duration">{duration}</span> : null}</div>;
              })
                : release ? <div className="muted">{t("lucida.tracklist_empty")}</div> : null}
        </div> : null}
      </div>
    );
  }

  const statusText = unavailable
    ? t("lucida.unavailable")
    : chromiumMissing
      ? t("lucida.chromium_required")
    : accessMissing
      ? t("lucida.access_required")
      : statusError
        ? resolveMessage(statusError)
        : ready
          ? t("lucida.ready")
          : t("lucida.checking");
  const statusClass = unavailable || statusError ? "status-line-danger" : chromiumMissing || accessMissing ? "status-line-warn" : ready ? "status-line-ok" : "status-line-pending";

  return (
    <div>
      <h1>{t("lucida.title")}</h1>
      <div className="comment">{t("lucida.subtitle")}</div>
      <div className="panel">
        <div className={clsx("status-line", statusClass)} role="status">
          <span className="status-line-marker" aria-hidden="true">●</span>
          <span>{statusText}</span>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <SegControl options={SERVICES} current={service} onChange={selectService} label={t("lucida.service")} />
          <button className={clsx("ghost", setupPending && "is-loading")} type="button" disabled={!canPrepareAccess} onClick={() => void prepareAccess()}>
            {t("lucida.prepare_access")}
          </button>
          {statusError ? <button className="ghost" type="button" onClick={() => void loadStatus(serviceRef.current)}>{t("lucida.refresh_status")}</button> : null}
        </div>
        {unavailable ? <div className="muted" style={{ marginTop: 8 }}>{t("lucida.unavailable_hint")}</div> : null}
        {chromiumMissing ? <div className="muted" style={{ marginTop: 8 }}>{t("lucida.chromium_hint")}</div> : null}
        {accessMissing ? <div className="muted" style={{ marginTop: 8 }}>{t("lucida.access_hint")}</div> : null}
      </div>

      <label className="visually-hidden" htmlFor="lucida-query">{t("lucida.query")}</label>
      <div className="row">
        <div className="grow">
          <input id="lucida-query" type="text" value={query} placeholder={t("lucida.placeholder")} disabled={!ready} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void search(); }} />
        </div>
        <button type="button" className={clsx(searching && "is-loading")} disabled={!ready || !query.trim() || searching} onClick={() => void search()}>
          {searching ? t("search.searching") : t("search.action")}
        </button>
      </div>

      <div style={{ marginTop: 16 }}>
        <OpPanels ops={ops} />
        {searchError ? <div className="panel" style={{ borderColor: "var(--danger)" }}>{resolveMessage(searchError)}</div> : null}
        {results ? (
          results.albums.length || results.tracks.length ? (
            <>
               {results.albums.length ? <><h2>{t("lucida.albums")}</h2><div className="lucida-albums-grid lucida-results-grid" data-testid="lucida-albums-grid">{results.albums.map((item, index) => <div className="lucida-result-card" key={`album:${item.url}`}>{renderItem(item, "album", results.service, index)}</div>)}</div></> : null}
               {results.tracks.length ? <><h2>{t("lucida.tracks")}</h2><div className="lucida-tracks-grid lucida-results-grid" data-testid="lucida-tracks-grid">{results.tracks.map((item, index) => <div className="lucida-result-card" key={`track:${item.url}`}>{renderItem(item, "track", results.service, index)}</div>)}</div></> : null}
            </>
          ) : <EmptyState art="∅" title={t("lucida.empty")} sub={t("lucida.empty_hint")} />
        ) : null}
      </div>
    </div>
  );
}
