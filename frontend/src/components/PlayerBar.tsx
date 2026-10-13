/* Единый sticky-плеер внизу экрана (классы #playerbar/.pb-*). */
import { useEffect } from "react";
import { currentAudio, onAudio, usePlayer } from "../stores/player";
import { AudioPlayer } from "./AudioPlayer";
import { Icon } from "./ui/Icon";
import { useTranslation } from "react-i18next";

export function PlayerBar() {
  const { t } = useTranslation();
  const src = usePlayer((s) => s.src);
  const title = usePlayer((s) => s.title);
  const artist = usePlayer((s) => s.artist);
  const coverUrl = usePlayer((s) => s.coverUrl);
  const visible = usePlayer((s) => s.visible);
  const seq = usePlayer((s) => s.seq);
  const hide = usePlayer((s) => s.hide);

  // Отступ контента, пока плеер виден.
  useEffect(() => {
    document.body.classList.toggle("pb-offset", visible);
    return () => document.body.classList.remove("pb-offset");
  }, [visible]);

  // Media Session: метаданные трека + состояние воспроизведения.
  useEffect(() => {
    if (!visible || !("mediaSession" in navigator)) return;
    try {
        navigator.mediaSession.metadata = new MediaMetadata({ title: title || t("player.preview"), artist: artist || "" });
    } catch {
      /* ignore */
    }
  }, [visible, title, artist, t]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    const sync = () => {
      try {
        const el = currentAudio();
        navigator.mediaSession.playbackState = el && !el.paused ? "playing" : "paused";
      } catch {
        /* ignore */
      }
    };
    const off1 = onAudio("play", sync);
    const off2 = onAudio("pause", sync);
    return () => {
      off1();
      off2();
    };
  }, [visible]);

  if (!visible) return null;

  return (
    <div id="playerbar" className="show">
      <div className="pb-inner">
        {coverUrl ? <img className="pb-cover" src={coverUrl} alt="" /> : null}
        <div className="pb-meta">
          <div className="pb-title">{title || t("player.preview")}</div>
          <div className="pb-artist">{artist}</div>
        </div>
        <div className="pb-player">
          <AudioPlayer src={src} seq={seq} />
        </div>
        <button
          className="ghost iconbtn pb-close"
          type="button"
          title={t("player.close")}
          aria-label={t("player.close")}
          onClick={hide}
        >
          <Icon name="x" />
        </button>
      </div>
    </div>
  );
}
