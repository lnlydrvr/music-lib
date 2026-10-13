/* Строки YT-треков: полная (радио/скачивание/пометки) и минимальная
   (.lib-grid minimal — как локальные треки альбома). */
import type { ReactNode } from "react";
import { fmtDuration } from "../../lib/format";
import { TrackRow } from "../../components/ui/TrackRow";
import { ClipBadge, InLibBadge } from "./badges";
import type { YTMTrack } from "./types";
import { useTranslation } from "react-i18next";

export function isClip(t: Pick<YTMTrack, "video_type">): boolean {
  return !!t.video_type && t.video_type !== "MUSIC_VIDEO_TYPE_ATV";
}

export function DownloadButton({ track, onDownload }: { track: YTMTrack; onDownload: (t: YTMTrack) => void }) {
  const { t } = useTranslation();
  return (
    <button
      className="small-btn"
      type="button"
      title={t("ytm.download.title")}
      aria-label={t("ytm.download.track_aria", { title: track.title || track.video_id })}
      onClick={() => onDownload(track)}
    >
      ↓
    </button>
  );
}

export function RadioButton({ track, onRadio }: { track: YTMTrack; onRadio: (t: YTMTrack) => void }) {
  const { t } = useTranslation();
  return (
    <button
      className="small-btn ghost"
      type="button"
      title={t("ytm.radio.title")}
      aria-label={t("ytm.radio.track_aria", { title: track.title || track.video_id })}
      onClick={() => onRadio(track)}
    >
      {t("ytm.radio.button")}
    </button>
  );
}

/* Строка YT-трека для списков «Все треки»: не файл — без чекбокса/выбора,
   только обложка, мета, «Радио», скачивание/пометка. */
export function YtmTrackRow({
  track,
  onDownload,
  onRadio,
  radio = true,
}: {
  track: YTMTrack;
  onDownload: (t: YTMTrack) => void;
  onRadio?: (t: YTMTrack) => void;
  radio?: boolean;
}) {
  const meta = [track.year ? String(track.year) : "", fmtDuration(track.duration)].filter(Boolean).join(" · ");
  const actions: ReactNode[] = [];
  if (radio) actions.push(<RadioButton key="radio" track={track} onRadio={onRadio ?? (() => {})} />);
  if (track.in_library) actions.push(<InLibBadge key="lib" />);
  else actions.push(<DownloadButton key="dl" track={track} onDownload={onDownload} />);
  if (isClip(track)) actions.push(<ClipBadge key="clip" />);
  return (
    <TrackRow
      coverSrc={track.cover_url}
      title={track.title || track.video_id}
      sub={track.artist || ""}
      meta={meta}
      actions={actions}
    />
  );
}

/* Список YT-треков тем же списком, что и локальные треки альбома:
   минимальные строки .lib-grid (значок/скачивание · обложка · строка · YT/длина). */
export function MinimalTrackRows({
  tracks,
  onDownload,
}: {
  tracks: YTMTrack[];
  onDownload: (t: YTMTrack) => void;
}) {
  const { t } = useTranslation();
  if (!tracks.length) return <div className="empty">{t("ytm.no_tracks")}</div>;
  return (
    <div className="lib-grid" data-density="minimal">
      {tracks.map((track, i) => {
        const name = `${track.title || track.video_id || ""}${track.artist ? ` — ${track.artist}` : ""}`;
        return (
          <div className="lib-card" aria-label={name} key={track.video_id || i}>
            {track.in_library ? <InLibBadge /> : <DownloadButton track={track} onDownload={onDownload} />}
            <div className="lib-cover">
              {track.cover_url ? (
                <img src={track.cover_url} loading="lazy" alt={t("ytm.cover_alt", { title: name })} />
              ) : (
                <div className="lib-nocover" aria-hidden="true">♫</div>
              )}
            </div>
            <div className="lib-mid">
              <div className="lib-title">{track.title || track.video_id || ""}</div>
              <div className="lib-sub">{track.artist || ""}</div>
            </div>
            <div className="lib-rowline">{name}</div>
            <div className="lib-cols">
              {track.track_number ? (
                <span className="lc-num" title={t("ytm.track_number")}>
                  {String(track.track_number).split("/")[0].trim()}
                </span>
              ) : null}
              <span className="lc-fmt" title={t("ytm.source")}>YT</span>
              {track.duration ? <span className="lc-dur">{fmtDuration(track.duration)}</span> : null}
              {isClip(track) ? <ClipBadge /> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
