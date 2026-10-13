/* Плашки-пометки YouTube Music: «в библиотеке», «клип», N/M заполненность. */
import clsx from "clsx";
import { useTranslation } from "react-i18next";

const CHECK_SVG =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

export function InLibBadge() {
  const { t } = useTranslation();
  return (
    <span
      className="tag ok"
      title={t("ytm.track_in_library")}
      aria-label={t("ytm.in_library")}
      dangerouslySetInnerHTML={{ __html: CHECK_SVG }}
    />
  );
}

export function ClipBadge() {
  const { t } = useTranslation();
  return (
    <span className="tag" style={{ opacity: ".8" }} title={t("ytm.clip_title")}>
      {t("ytm.clip")}
    </span>
  );
}

/* Плашка «N/M» по заполненности альбома в библиотеке:
   ● полный (зелёный), ◐ частичный (>0.5 — жёлтый, иначе красный),
   ○ пусто (красный); без общего числа — «N тр.». */
export function CountBadge({ have, total, extra = "" }: { have: number; total: number; extra?: string }) {
  const { t } = useTranslation();
  if (total && have >= total) {
    return (
      <span className={clsx("tag", "ok", extra)} title={t("ytm.album_in_library")}>
        {`● ${have}/${total}`}
      </span>
    );
  }
  if (have > 0) {
    const cls = total && have / total > 0.5 ? "warn" : "bad";
    return (
      <span className={clsx("tag", cls, extra)} title={t("ytm.album_partial")}>
        {`◐ ${have}/${total}`}
      </span>
    );
  }
  if (total) {
    return (
      <span className={clsx("tag", "bad", extra)} title={t("ytm.album_missing")}>
        {`○ 0/${total}`}
      </span>
    );
  }
  return <span className={clsx("tag", extra)}>{t("ytm.short_tracks", { count: have })}</span>;
}

/* Плашка «N/M» как оверлей на обложке альбома. */
export function AlbumBadge({ album }: { album: { track_count?: number; in_library_tracks?: number } }) {
  const { t } = useTranslation();
  const total = album.track_count || album.in_library_tracks || 0;
  const have = album.in_library_tracks || 0;
  if (!total && !have) {
    return (
      <span className="tag bad lib-album-badge" title={t("ytm.album_missing")}>
        {`○ ${t("ytm.album_none")}`}
      </span>
    );
  }
  return <CountBadge have={have} total={total} extra="lib-album-badge" />;
}
