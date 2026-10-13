/* Детали альбома/исполнителя/плейлиста YouTube Music и панель радио. */
import { useEffect, useState, type ReactNode } from "react";
import { get } from "../../lib/api";
import { fmtDuration } from "../../lib/format";
import { TrackRow } from "../../components/ui/TrackRow";
import { PreviewButton } from "../../components/PreviewButton";
import { AlbumBadge } from "./badges";
import { AlbumCard } from "./cards";
import { MinimalTrackRows, DownloadButton, YtmTrackRow } from "./rows";
import { downloadAllLabel, ytmDownload, type YtmDownloadTarget } from "./download";
import type { YTMArtistDetail, YTMAlbumDetail, YTMPlaylistDetail, YTMTrack } from "./types";
import { useTranslation } from "react-i18next";
import type { TranslationKey } from "../../i18n/messages";
import { asRenderableMessage, resolveMessage } from "../../i18n/messages";

export interface YtmDetailOpts {
  onDownload?: (items: YTMTrack[], target: YtmDownloadTarget, onDone?: () => void) => void;
  back?: () => void;
}

function ErrorPanel({ e }: { e: unknown }) {
  return <div className="panel" style={{ borderColor: "var(--danger)" }}>{resolveMessage(asRenderableMessage(e))}</div>;
}

function BackButton({ back }: { back?: () => void }) {
  const { t } = useTranslation();
  if (!back) return null;
  return (
    <button className="ghost small-btn" type="button" onClick={back}>
      {t("ytm.back")}
    </button>
  );
}

/* Кнопка «Скачать отсутствующие (N)» по списку треков. */
export function DownloadAllButton({
  items,
  target,
  onDownload,
  labelKey,
}: {
  items: YTMTrack[];
  target: YtmDownloadTarget;
  onDownload?: (items: YTMTrack[], target: YtmDownloadTarget, onDone?: () => void) => void;
  labelKey?: Extract<TranslationKey, `ytm.download.${string}`>;
}) {
  const missing = items.filter((t) => !t.in_library);
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={!missing.length || busy}
      onClick={async () => {
        setBusy(true);
        try {
          if (onDownload) await onDownload(missing, target);
          else await ytmDownload(missing, target);
        } finally {
          setBusy(false);
        }
      }}
    >
      {downloadAllLabel(missing.length, labelKey)}
    </button>
  );
}

/* --- Детали альбома --- */
export function AlbumDetail({ id, back, onDownload, title }: YtmDetailOpts & { id: string; title?: string }) {
  const { t } = useTranslation();
  const [data, setData] = useState<YTMAlbumDetail | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    get<YTMAlbumDetail>("/api/ytmusic/album", { browse_id: id })
      .then((a) => alive && setData(a))
      .catch((e) => alive && setError(e));
    return () => {
      alive = false;
    };
  }, [id]);

  if (error) return <ErrorPanel e={error} />;
  if (!data) return <div className="comment">{t("ytm.loading_album")}</div>;
  const showTitle = title || data.title || t("ytm.album");
  const downloadTarget = { kind: "album", providerId: data.id || id, title: { code: "ytm.download.album_name", params: { title: showTitle } } } satisfies YtmDownloadTarget;
  return (
    <div>
      <BackButton back={back} />
      <div className="row" style={{ justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div>
          <b>{showTitle}</b>
          <div className="muted">
            {[data.artist, data.year ? String(data.year) : "", data.track_count ? t("ytm.tracks.count", { count: data.track_count }) : ""]
              .filter(Boolean)
              .join(" · ")}
          </div>
        </div>
        <AlbumBadge album={data} />
      </div>
      <div className="row" style={{ margin: "8px 0" }}>
        <DownloadAllButton items={data.tracks} target={downloadTarget} onDownload={onDownload} />
      </div>
      <MinimalTrackRows tracks={data.tracks} onDownload={(t) => void ytmDownload([t], downloadTarget)} />
    </div>
  );
}

/* --- Детали исполнителя --- */
/* localCards — готовые карточки локальных альбомов (дедуп с YT, фаза 3/заход 2),
   ytAlbumFiltered — предикат «этот YT-альбом уже показан локально». */
export function ArtistDetail({
  id,
  back,
  name,
  onDownload,
  localCards = [],
  localCount = 0,
  ytAlbumFiltered = null,
  onOpenAlbum = null,
}: YtmDetailOpts & {
  id: string;
  name?: string;
  localCards?: ReactNode[];
  localCount?: number;
  ytAlbumFiltered?: ((a: YTMAlbumDetail) => boolean) | null;
  onOpenAlbum?: ((albumId: string, title: string) => void) | null;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<YTMArtistDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [albumId, setAlbumId] = useState<string | null>(null);
  const [albumTitle, setAlbumTitle] = useState("");

  useEffect(() => {
    if (!id) return;
    let alive = true;
    setData(null);
    setError(null);
    get<YTMArtistDetail>("/api/ytmusic/artist", { browse_id: id })
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e));
    return () => {
      alive = false;
    };
  }, [id]);

  if (albumId) {
    return (
      <AlbumDetail
        id={albumId}
        title={albumTitle}
        onDownload={onDownload}
        back={() => setAlbumId(null)}
      />
    );
  }
  if (error) return <ErrorPanel e={error} />;
  if (!data) return <div className="comment">{t("ytm.loading_artist")}</div>;

  const showName = name || data.name || t("ytm.artist_label");
  const artistTarget = { kind: "artist", providerId: data.id || id, title: { code: "ytm.download.artist_name", params: { title: showName } } } satisfies YtmDownloadTarget;
  const top = data.top_songs || [];
  const ytAlbums = (data.albums || []).filter(
    (al) => !(ytAlbumFiltered && ytAlbumFiltered(al as unknown as YTMAlbumDetail)),
  );
  const bits = [data.subscribers || "", localCount ? t("ytm.artist.local_count", { count: localCount }) : ""]
    .filter(Boolean)
    .join(" · ");

  return (
    <div>
      <div className="panel lib-album-head lib-artist-head">
        <div className="lib-artist-back">
          <BackButton back={back} />
        </div>
        {data.cover_url ? (
          <img src={data.cover_url} className="lib-bigcover round" alt={t("ytm.artist_photo", { name: showName })} />
        ) : (
          <div className="lib-nocover big round" aria-hidden="true">♫</div>
        )}
        <div className="lib-album-meta">
          <div className="lib-album-title">{showName}</div>
          {bits ? <div className="muted">{bits}</div> : null}
          {onDownload && top.length ? (
            <div style={{ marginTop: 8 }}>
              <DownloadAllButton
                items={top}
                target={artistTarget}
                onDownload={onDownload}
                labelKey="ytm.download.popular"
              />
            </div>
          ) : null}
        </div>
      </div>
      {localCards.length || ytAlbums.length ? (
        <>
          <div style={{ margin: "16px 0 8px" }}>
            <b>{t("ytm.albums")}</b>
          </div>
          <div className="lib-grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 10 }}>
            {localCards.map((c, i) => (
              <div key={i}>{c}</div>
            ))}
            {ytAlbums.map((al) => (
              <AlbumCard
                key={al.id}
                album={al}
                onOpen={() => {
                  if (onOpenAlbum) onOpenAlbum(al.id, al.title || "");
                  else {
                    setAlbumId(al.id);
                    setAlbumTitle(al.title || "");
                  }
                }}
              />
            ))}
          </div>
        </>
      ) : null}
      {top.length ? (
        <>
          <div style={{ margin: "16px 0 8px" }}>
            <b>{t("ytm.popular")}</b>
          </div>
          <MinimalTrackRows tracks={top} onDownload={(t) => void ytmDownload([t], artistTarget)} />
        </>
      ) : showName ? (
        <YtTopSection artist={showName} onDownload={onDownload} />
      ) : null}
    </div>
  );
}

/* Строка «Топ на YouTube»: превью + скачивание через пайплайн YT Music. */
function YtTopRow({ r, artist, onDownload }: { r: YtSearchResult; artist: string; onDownload?: YtmDetailOpts["onDownload"] }) {
  const { t } = useTranslation();
  const target = { kind: "youtube", providerId: r.id, title: { code: "ytm.download.youtube_name", params: { title: artist } } } satisfies YtmDownloadTarget;
  return (
    <TrackRow
      coverSrc={r.thumbnail || ""}
      title={r.title || t("common.empty_value")}
      sub={r.uploader || ""}
      meta={fmtDuration(r.duration)}
      actions={
        <>
          <PreviewButton url={r.url} title={r.title} />
          <DownloadButton
            track={{ video_id: r.id, title: r.title, artist, cover_url: r.thumbnail || "" }}
            onDownload={(t) =>
              onDownload
                ? onDownload([t], target)
                : void ytmDownload([t], target)
            }
          />
        </>
      }
    />
  );
}

interface YtSearchResult {
  id: string;
  title: string;
  uploader: string;
  duration: number;
  url: string;
  thumbnail: string;
}

/* Фолбэк, когда у исполнителя нет top_songs: топ по поиску YouTube Music,
   а без подключения — обычный YouTube (yt-dlp). */
function YtTopSection({ artist, onDownload }: { artist: string; onDownload?: YtmDetailOpts["onDownload"] }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<ReactNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [radioSeed, setRadioSeed] = useState<YTMTrack | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      let out: ReactNode[] = [];
      try {
        const res = await get<{ tracks: YTMTrack[] }>("/api/ytmusic/search", { q: artist, limit: 8 });
          out = (res.tracks || []).map((t, i) => (
          <YtmTrackRow key={t.video_id || i} track={t} onDownload={(x) => void ytmDownload([x], { kind: "track", providerId: x.video_id, title: { code: "ytm.download.youtube_name", params: { title: artist } } })} onRadio={setRadioSeed} />
        ));
      } catch {
        /* YT Music недоступен — обычный YouTube ниже */
      }
      if (!alive) return;
      if (!out.length) {
        try {
          const res = await get<YtSearchResult[]>("/api/search", { q: artist, limit: 8 });
          out = res.map((r, i) => <YtTopRow key={r.id || i} r={r} artist={artist} onDownload={onDownload} />);
        } catch {
          /* ниже покажем пусто */
        }
      }
      if (!alive) return;
      setRows(out);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [artist, onDownload]);

  return (
    <div>
      <div style={{ margin: "16px 0 8px" }}>
        <b>{t("ytm.top_tracks")}</b>
      </div>
      {radioSeed ? <RadioPanel seed={radioSeed} onClose={() => setRadioSeed(null)} /> : null}
      {loading ? <div className="comment">{t("ytm.finding_popular")}</div> : null}
      {!loading && !rows.length ? <div className="empty">{t("ytm.not_found")}</div> : null}
      {!loading && rows.length ? <div style={{ display: "grid", gap: 6 }}>{rows}</div> : null}
    </div>
  );
}

/* --- Детали плейлиста --- */
export function PlaylistDetail({ id, back, onDownload }: YtmDetailOpts & { id: string }) {
  const { t } = useTranslation();
  const [data, setData] = useState<YTMPlaylistDetail | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    get<YTMPlaylistDetail>("/api/ytmusic/playlist", { playlist_id: id })
      .then((pl) => alive && setData(pl))
      .catch((e) => alive && setError(e));
    return () => {
      alive = false;
    };
  }, [id]);

  if (error) return <ErrorPanel e={error} />;
  if (!data) return <div className="comment">{t("ytm.loading_playlist")}</div>;
  return (
    <div>
      <BackButton back={back} />
      <b>{data.title || t("ytm.playlist")}</b>
      <div className="comment">
        {[data.track_count ? t("ytm.tracks.count", { count: data.track_count }) : "", data.description].filter(Boolean).join(" · ")}
      </div>
      <div className="row" style={{ margin: "8px 0" }}>
        <DownloadAllButton items={data.tracks} target={{ kind: "playlist", providerId: data.id || id, title: { code: "ytm.download.playlist_name", params: { title: data.title || id } } }} onDownload={onDownload} />
      </div>
      <MinimalTrackRows tracks={data.tracks} onDownload={(t) => void ytmDownload([t], { kind: "playlist", providerId: data.id || id, title: { code: "ytm.download.playlist_name", params: { title: data.title || id } } })} />
    </div>
  );
}

/* --- Радио (watch_playlist) --- */
export function RadioPanel({
  seed,
  onClose,
  onDownload,
}: {
  seed: YTMTrack;
  onClose: () => void;
  onDownload?: (items: YTMTrack[], target: YtmDownloadTarget, onDone?: () => void) => void;
}) {
  const { t } = useTranslation();
  const [tracks, setTracks] = useState<YTMTrack[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!seed || !seed.video_id) return;
    let alive = true;
    setTracks(null);
    setError(null);
    get<{ tracks: YTMTrack[] }>("/api/ytmusic/radio", { video_id: seed.video_id, limit: 25 })
      .then((res) => alive && setTracks(res.tracks || []))
      .catch((e) => alive && setError(e));
    return () => {
      alive = false;
    };
  }, [seed]);

  if (!seed || !seed.video_id) return null;
  const radioName = seed.title || seed.video_id;
  const radioTarget = { kind: "radio", providerId: seed.video_id, title: { code: "ytm.download.radio_name", params: { title: radioName } } } satisfies YtmDownloadTarget;
  return (
    <div className="panel" style={{ margin: "10px 0" }}>
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <div>
          <b>{t("ytm.similar")}</b>
          <span className="muted">{` ${seed.artist ? `${seed.artist} — ` : ""}${seed.title || ""}`}</span>
        </div>
        <button className="ghost small-btn" type="button" aria-label={t("ytm.close_aria")} onClick={onClose}>
          ×
        </button>
      </div>
      <div style={{ marginTop: 8 }}>
        {error ? (
          <ErrorPanel e={error} />
        ) : tracks == null ? (
          <div className="comment">{t("common.loading")}</div>
        ) : !tracks.length ? (
          <div className="empty">{t("ytm.similar_empty")}</div>
        ) : (
          <>
            <div className="row" style={{ marginBottom: 8 }}>
              <DownloadAllButton
                items={tracks}
                target={radioTarget}
                onDownload={onDownload}
              />
            </div>
            <MinimalTrackRows tracks={tracks} onDownload={(t) => void ytmDownload([t], radioTarget)} />
          </>
        )}
      </div>
    </div>
  );
}
