/* Мини-плеер: кнопка play/pause + кликабельный aria-слайдер позиции. */
import { useEffect, useRef, useState } from "react";
import { SVG_PLAY } from "./ui/Icon";
import { attachAudio } from "../stores/player";
import { useTranslation } from "react-i18next";

function fmtTime(s: number): string {
  const t = Math.floor(s || 0);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

function safePlay(el: HTMLAudioElement) {
  try {
    const p = el.play() as unknown;
    if (p && typeof (p as Promise<void>).catch === "function") (p as Promise<void>).catch(() => {});
  } catch {
    /* ignore */
  }
}

export function AudioPlayer({ src, seq }: { src: string; seq: number }) {
  const { t } = useTranslation();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [cur, setCur] = useState(0);
  const [dur, setDur] = useState(0);

  // Регистрация <audio> в сторе плеера (эмиттер событий для вьюх).
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    attachAudio(el);
    return () => attachAudio(null);
  }, []);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onLoaded = () => {
      setDur(el.duration || 0);
      setLoaded(true);
    };
    const onTime = () => setCur(el.currentTime);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("loadedmetadata", onLoaded);
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("ended", onPause);
    return () => {
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("loadedmetadata", onLoaded);
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("ended", onPause);
    };
  }, []);

  // Смена трека (или повторный play того же src): перезапуск с нуля.
  useEffect(() => {
    const el = audioRef.current;
    if (!el || !src) return;
    el.src = src;
    setLoaded(false);
    setCur(0);
    setDur(0);
    safePlay(el);
  }, [src, seq]);

  const pct = dur ? (cur / dur) * 100 : 0;

  const seekRatio = (ratio: number) => {
    const el = audioRef.current;
    if (!el || !el.duration) return;
    el.currentTime = Math.max(0, Math.min(1, ratio)) * el.duration;
    setCur(el.currentTime);
  };

  return (
    <div className={`audio-player${loaded ? " loaded" : ""}`}>
      <button
        className="small-btn audio-play"
        type="button"
        title={t(playing ? "player.pause" : "player.play")}
        aria-label={t(playing ? "player.pause" : "player.play")}
        aria-pressed={playing}
        onClick={() => {
          const el = audioRef.current;
          if (!el || !el.src) return;
          if (el.paused) safePlay(el);
          else el.pause();
        }}
      >
        {SVG_PLAY}
      </button>
      <div
        className="audio-bar"
        tabIndex={0}
        role="slider"
        aria-label={t("player.position")}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={dur ? Math.round(pct) : 0}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          seekRatio((e.clientX - r.left) / r.width);
        }}
        onKeyDown={(e) => {
          const el = audioRef.current;
          if (!el || !el.duration) return;
          const step = 5 / el.duration;
          const curR = el.currentTime / el.duration;
          if (e.key === "ArrowRight" || e.key === "ArrowUp") {
            e.preventDefault();
            seekRatio(curR + step);
          } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
            e.preventDefault();
            seekRatio(curR - step);
          } else if (e.key === "Home") {
            e.preventDefault();
            seekRatio(0);
          } else if (e.key === "End") {
            e.preventDefault();
            seekRatio(1);
          }
        }}
      >
        <div className="audio-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="audio-time">{fmtTime(cur)}</span>
      <span className="audio-sep">/</span>
      <span className="audio-time">{fmtTime(dur)}</span>
      <audio ref={audioRef} preload="none" />
    </div>
  );
}
