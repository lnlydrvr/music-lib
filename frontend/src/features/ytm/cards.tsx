/* Карточки YouTube Music: альбом, исполнитель, строка плейлиста. */
import type { ReactNode } from "react";
import { AlbumBadge, CountBadge } from "./badges";
import type { YTMArtist, YTMAlbum, YTMPlaylist } from "./types";
import { useTranslation } from "react-i18next";

function openOnKey(onOpen?: () => void) {
  return (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpen?.();
    }
  };
}

/* Карточка YT-альбома. a = {id, title, artist, year, track_count, in_library_tracks, cover_url}. */
export function AlbumCard({
  album,
  onOpen,
  actions = null,
}: {
  album: YTMAlbum;
  onOpen?: (a: YTMAlbum) => void;
  actions?: ReactNode;
}) {
  const { t } = useTranslation();
  const total = album.track_count || album.in_library_tracks || 0;
  const have = album.in_library_tracks || 0;
  const subCount = total || have ? <CountBadge have={have} total={total} extra="lib-count" /> : null;
  return (
    <div
      className="lib-card album"
      tabIndex={0}
      role="button"
      aria-label={t("ytm.album_aria", { title: album.title || "", artist: album.artist ? ` — ${album.artist}` : "" })}
      onClick={() => onOpen?.(album)}
      onKeyDown={openOnKey(() => onOpen?.(album))}
    >
      <div className="lib-cover">
        {album.cover_url ? (
          <img src={album.cover_url} loading="lazy" alt={t("ytm.album_cover", { title: album.title || "" })} />
        ) : (
          <div className="lib-nocover" aria-hidden="true">♫</div>
        )}
        <AlbumBadge album={album} />
      </div>
      <div className="lib-mid">
        <div className="lib-title">{album.title || "—"}</div>
        <div className="lib-sub lib-sub-row">
          <span className="lib-sub-text">{album.artist || ""}</span>
          {subCount}
        </div>
      </div>
      {actions ? <div className="row lib-acts">{actions}</div> : null}
    </div>
  );
}

/* Карточка исполнителя. a = {id, name, subscribers, cover_url, local_count}. */
export function ArtistCard({
  artist,
  onOpen,
  subscribed = false,
  actions = null,
}: {
  artist: YTMArtist;
  onOpen?: (a: YTMArtist) => void;
  subscribed?: boolean;
  actions?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div
      className="lib-card album"
      tabIndex={0}
      role="button"
      aria-label={t("ytm.artist_aria", { name: artist.name || "" })}
      onClick={() => onOpen?.(artist)}
      onKeyDown={openOnKey(() => onOpen?.(artist))}
    >
      <div className="lib-cover">
        {artist.cover_url ? (
          <img src={artist.cover_url} loading="lazy" alt={t("ytm.artist_photo", { name: artist.name || "" })} />
        ) : (
          <div className="lib-nocover" aria-hidden="true">♫</div>
        )}
        {artist.local_count ? (
          <span className="tag ok" title={t("ytm.files_in_library")}>
            {`${t("ytm.artist.local_count", { count: artist.local_count })}${subscribed ? ` · ${t("ytm.subscribed")}` : ""}`}
          </span>
        ) : subscribed ? (
          <span className="tag" title={t("ytm.subscription")}>{t("ytm.subscribed")}</span>
        ) : null}
      </div>
      <div className="lib-mid">
        <div className="lib-title">{artist.name || "—"}</div>
        {artist.subscribers ? <div className="lib-sub">{t("ytm.subscribers", { value: artist.subscribers })}</div> : null}
      </div>
      {actions ? <div className="row lib-acts" style={{ marginTop: 6 }}>{actions}</div> : null}
    </div>
  );
}

/* Строка плейлиста. pl = {id, title, count, cover_url, description, local_count}. */
export function PlaylistRow({ playlist, onOpen }: { playlist: YTMPlaylist; onOpen?: (pl: YTMPlaylist) => void }) {
  const { t } = useTranslation();
  const have = playlist.local_count || 0;
  const total = playlist.count || 0;
  return (
    <button
      className="trackrow"
      type="button"
      style={{ textAlign: "start", cursor: "pointer", width: "100%" }}
      onClick={() => onOpen?.(playlist)}
    >
      <span className="cover cover-48">
        {playlist.cover_url ? (
          <img src={playlist.cover_url} loading="lazy" alt={t("ytm.cover_alt", { title: playlist.title || "" })} />
        ) : (
          <span aria-hidden="true">♫</span>
        )}
      </span>
      <span className="t-main">
        <span className="t-title">{playlist.title || t("ytm.playlist")}</span>
        {playlist.description ? <span className="t-sub">{playlist.description}</span> : null}
      </span>
      <span className="t-meta">
        {have ? (
          <span style={{ display: "block", marginBottom: 2 }}>
            <CountBadge have={have} total={total} extra="lib-count" />
          </span>
        ) : null}
        <span style={{ display: "block" }}>{total ? t("ytm.tracks.count", { count: total }) : ""}</span>
      </span>
    </button>
  );
}
