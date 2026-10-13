/* Карточки «Библиотеки»: локальный трек (с чекбоксом), YT-трек без файла,
   локальный/объединённый альбом, локальный исполнитель. */
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { coverUrl } from "../../lib/api";
import { fmtDuration, fmtSize } from "../../lib/format";
import { CountBadge } from "../../features/ytm/badges";
import { AlbumCard } from "../../features/ytm/cards";
import { isClip } from "../../features/ytm/rows";
import type { YTMAlbum, YTMTrack } from "../../features/ytm/types";
import { normKey, pickName, stemOf, type AlbumGroup, type TrackRow } from "./libUtils";

function openOnKey(open: () => void) {
  return (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      open();
    }
  };
}

function NoCover() {
  return <div className="lib-nocover" aria-hidden="true">♫</div>;
}

/* Единая карточка трека: «Все треки» и треки внутри альбома одинаковы.
   ytBadge — трек лайкнут в аккаунте YT Music: бейдж «♥ YT». */
export function TrackCard({
  t,
  showNum = false,
  ytBadge = false,
  selected,
  active = false,
  onToggleSelect,
  onOpen,
}: {
  t: TrackRow;
  showNum?: boolean;
  ytBadge?: boolean;
  selected: boolean;
  active?: boolean;
  onToggleSelect: (path: string) => void;
  onOpen: (t: TrackRow) => void;
}) {
  const { t: translate } = useTranslation();
  const num = showNum && t.track_number ? String(t.track_number).split("/")[0].trim() : "";
  const cardName = `${t.title || stemOf(t.path)}${t.artist ? ` — ${t.artist}` : ""}`;
  return (
    <div
      className={clsx("lib-card", selected && "chk", active && "active")}
      data-path={t.path}
      tabIndex={0}
      role="button"
      aria-label={translate("library.card.open_track_aria", { name: cardName })}
      onClick={() => onOpen(t)}
      onKeyDown={openOnKey(() => onOpen(t))}
    >
      {/* label-обёртка: тач-таргет чекбокса расширяется паддингом до ≥44px. */}
      <label className="lib-check" onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          aria-label={translate("quality.selection.track_aria", { name: cardName })}
          checked={selected}
          onChange={() => onToggleSelect(t.path)}
        />
      </label>
      <div className="lib-cover">
        {t.has_cover ? (
          <img
            src={coverUrl(t.path)}
            loading="lazy"
            alt={translate("common.cover_alt", { title: `${t.artist ? `${t.artist} — ` : ""}${t.title || stemOf(t.path)}` })}
          />
        ) : (
          <NoCover />
        )}
        {t.need_compress ? <span className="tag bad lib-compress">{translate("library.compress.needed_short")}</span> : null}
        {ytBadge ? <span className="tag warn lib-yt-badge" title={translate("library.ytm.liked_title")}>♥ YT</span> : null}
      </div>
      <div className="lib-mid">
        <div className="lib-title">{t.title || stemOf(t.path)}</div>
        <div className="lib-sub">{num ? `${num}. ${t.artist || ""}` : t.artist || ""}</div>
      </div>
      <div className="lib-rowline">{cardName}</div>
      <div className="lib-cols">
        {num ? (
          <span className="lc-num" title={translate("editor.fields.track_number")}>{num}</span>
        ) : null}
        {t.year ? <span className="lc-year">{t.year}</span> : null}
        <span className="lc-fmt" title={translate("library.card.format_title")}>{(t.ext || "").replace(/^\./, "").toUpperCase() || "—"}</span>
        <span className="lc-bit" title={translate("library.card.bitrate_title")}>{t.bitrate ? `${t.bitrate}k` : "—"}</span>
        <span className="lc-dur">{fmtDuration(t.duration_seconds) || "—"}</span>
        <span className="lc-size">{fmtSize(t.size_bytes)}</span>
        {t.need_compress ? <span className="tag bad">{translate("library.compress.needed_short")}</span> : null}
        {ytBadge ? <span className="lc-yt" title={translate("library.ytm.liked_title")}>♥ YT</span> : null}
      </div>
    </div>
  );
}

/* YT-карточка трека без локального файла: обложка, название, «Радио» и
   «Скачать»; у лайков — бейдж «♥». */
export function YtTrackCard({
  t,
  liked,
  onRadio,
  onDownload,
}: {
  t: YTMTrack;
  liked: boolean;
  onRadio: (t: YTMTrack) => void;
  onDownload: (t: YTMTrack) => void;
}) {
  const { t: translate } = useTranslation();
  const name = `${t.title || t.video_id || ""}${t.artist ? ` — ${t.artist}` : ""}`;
  return (
    <div className="lib-card yt" aria-label={translate("library.card.ytm_aria", { name })}>
      <div className="lib-cover" title={isClip(t) ? translate("library.card.clip_title") : undefined}>
        {t.cover_url ? <img src={t.cover_url} loading="lazy" alt={translate("ytm.cover_alt", { title: name })} /> : <NoCover />}
        {liked ? (
          <span className="tag warn lib-album-badge" title={translate("library.ytm.liked_title")}>♥</span>
        ) : null}
      </div>
      <div className="lib-mid">
        <div className="lib-title">{t.title || t.video_id || ""}</div>
        <div className="lib-sub">{t.artist || ""}</div>
      </div>
      <div className="lib-rowline">{name}</div>
      <div className="row lib-acts">
        <button className="small-btn ghost" type="button" title={translate("ytm.radio.title")} aria-label={translate("ytm.radio.track_aria", { title: t.title || t.video_id })} onClick={() => onRadio(t)}>
          {translate("ytm.radio.button")}
        </button>
        <button className="small-btn" type="button" title={translate("ytm.download.title")} aria-label={translate("ytm.download.track_aria", { title: t.title || t.video_id })} onClick={() => onDownload(t)}>
          ↓
        </button>
      </div>
    </div>
  );
}

/* Локальная карточка альбома (ya — YT-двойник для счётчика N/M). */
export function LocalAlbumCard({ g, ya, onOpen }: { g: AlbumGroup; ya?: YTMAlbum | null; onOpen: (g: AlbumGroup) => void }) {
  const { t } = useTranslation();
  const have = g.tracks.length;
  const total = ya ? ya.track_count || have : have;
  return (
    <div
      className="lib-card album"
      tabIndex={0}
      role="button"
      aria-label={g.artist ? t("library.card.open_album_artist_aria", { title: g.title, artist: g.artist, have, total }) : t("library.card.open_album_aria", { title: g.title, have, total })}
      onClick={() => onOpen(g)}
      onKeyDown={openOnKey(() => onOpen(g))}
    >
      <div className="lib-cover">
        {g.coverPath ? (
          <img src={coverUrl(g.coverPath)} loading="lazy" alt={t("library.card.album_cover_alt", { name: `${g.artist ? `${g.artist} — ` : ""}${g.title}` })} />
        ) : (
          <NoCover />
        )}
        {ya ? <CountBadge have={have} total={total} extra="lib-album-badge" /> : null}
      </div>
      <div className="lib-mid">
        <div className="lib-title">{g.title}</div>
        <div className="lib-sub lib-sub-row">
          <span className="lib-sub-text">{g.artist || ""}</span>
          {ya ? <CountBadge have={have} total={total} extra="lib-count" /> : null}
        </div>
      </div>
    </div>
  );
}

/* Альбом локальный + YT-двойник с большим числом треков → одна объединённая
   карточка N/M (имена — по настройке name_translit). */
export function MergedAlbumCard({
  g,
  ya,
  have,
  total,
  nameTranslit,
  onOpen,
}: {
  g: AlbumGroup;
  ya: YTMAlbum;
  have: number;
  total: number;
  nameTranslit: string;
  onOpen: (g: AlbumGroup) => void;
}) {
  const cover = g.coverPath ? coverUrl(g.coverPath) : ya.cover_url || "";
  return (
    <AlbumCard
      album={{
        id: ya.id,
        title: pickName(g.title, ya.title || "", nameTranslit),
        artist: pickName(g.artist, ya.artist || "", nameTranslit),
        track_count: total,
        in_library_tracks: have,
        cover_url: cover,
      }}
      onOpen={() => onOpen(g)}
    />
  );
}

/* Локальный исполнитель без YT-двойника. */
export function LocalArtistCard({
  a,
  onOpen,
}: {
  a: { name: string; count: number; coverPath: string | null };
  onOpen: (name: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      className="lib-card album"
      tabIndex={0}
      role="button"
      aria-label={t("library.card.artist_aria", { name: a.name, count: a.count })}
      onClick={() => onOpen(a.name)}
      onKeyDown={openOnKey(() => onOpen(a.name))}
    >
      <div className="lib-cover">
        {a.coverPath ? (
          <img src={coverUrl(a.coverPath)} loading="lazy" alt={t("ytm.cover_alt", { title: a.name })} />
        ) : (
          <NoCover />
        )}
        <span className="tag ok">{t("ytm.artist.local_count", { count: a.count })}</span>
      </div>
      <div className="lib-mid">
        <div className="lib-title">{a.name}</div>
        <div className="lib-sub">{t("library.artist.files", { count: a.count })}</div>
      </div>
    </div>
  );
}

/* Ключи лайков для бейджа «♥ YT» на локальных карточках. */
export function likedKeySet(liked: YTMTrack[]): Set<string> {
  return new Set(liked.map((t) => normKey(t.artist, t.title)).filter((k) => k !== "::"));
}
