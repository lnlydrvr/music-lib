/* Превью-кнопка: /api/preview → общий плеер (stores/player); подсветка
   «играет сейчас» синхронизируется с событиями глобального аудио. */
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { get } from "../lib/api";
import { toast } from "../lib/toast";
import { currentAudio, onAudio, usePlayer } from "../stores/player";
import { asRenderableMessage } from "../i18n/messages";
import { useTranslation } from "react-i18next";

const SVG_PLAY =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>';

export function PreviewButton({
  url,
  title = "",
  artist = "",
  coverUrl = "",
}: {
  url: string;
  title?: string;
  artist?: string;
  coverUrl?: string;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const currentRef = useRef("");

  useEffect(() => {
    const sync = () => {
      const a = currentAudio();
      setPlaying(!!a && !a.paused && currentRef.current === url);
    };
    const offs = ["play", "pause", "ended"].map((t) => onAudio(t, sync));
    sync();
    return () => offs.forEach((off) => off());
  }, [url]);

  return (
    <button
      className={clsx("small-btn", playing && "playing")}
      type="button"
      title={t("player.listen")}
      aria-label={t("player.listen_track", { title: title || t("player.preview") })}
      aria-pressed={playing}
      dangerouslySetInnerHTML={{ __html: SVG_PLAY }}
      disabled={loading}
      onClick={async () => {
        currentRef.current = url;
        setLoading(true);
        try {
          const res = await get<{ url: string }>("/api/preview", { url });
          usePlayer.getState().play({ src: res.url, title: title || t("player.preview"), artist, coverUrl });
        } catch (e) {
          toast(asRenderableMessage(e), "error");
        }
        setLoading(false);
      }}
    />
  );
}
