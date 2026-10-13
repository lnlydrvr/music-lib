/* Док фоновых задач снизу-справа: сворачивается/раскрывается, автоскрытие
   успешных через 5 сек, ошибки остаются до закрытия. Состояние — zustand
   (stores/downloads), этот компонент только рендерит (классы .dl-*). */
import { useEffect, useRef } from "react";
import clsx from "clsx";
import { downloadList, useDownloads } from "../stores/downloads";
import { useOverlays } from "../stores/overlays";
import { Icon } from "./ui/Icon";
import { StatusLine, type StatusKind } from "./ui/StatusLine";
import { resolveMessage } from "../i18n/messages";
import { useTranslation } from "react-i18next";

export function DownloadsDock() {
  const { t } = useTranslation();
  const items = useDownloads((s) => s.items);
  const expanded = useDownloads((s) => s.expanded);
  const toggle = useDownloads((s) => s.toggle);
  const dismiss = useDownloads((s) => s.dismiss);
  const clearFinished = useDownloads((s) => s.clearFinished);
  const barRef = useRef<HTMLButtonElement>(null);

  // Хвост истории задач после перезагрузки страницы.
  useEffect(() => {
    void useDownloads.getState().restore();
  }, []);

  // Esc сворачивает панель (если нет открытой модалки), фокус — на бар.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const st = useDownloads.getState();
      if (!st.expanded || useOverlays.getState().dialogCount > 0) return;
      st.toggle(false);
      if (document.activeElement === document.body) barRef.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const list = downloadList(items);
  const live = list.filter((i) => !i.removing);
  const active = list.filter((i) => i.status === "active");
  const errors = list.filter((i) => i.status === "error");
  const finished = list.some((i) => i.status !== "active" && !i.removing);

  let label = t("jobs.dock.title");
  if (active.length) {
    const withPct = active.filter((i) => i.percent != null);
    const avg = withPct.length
      ? Math.round(withPct.reduce((a, b, _, arr) => a + (b.percent as number) / arr.length, 0))
      : 0;
    label = t("jobs.dock.active", { count: active.length, percent: avg });
  } else if (errors.length) {
    label = t("jobs.dock.failed", { count: errors.length });
  } else if (live.length) {
    label = t("jobs.dock.ready");
  }

  const state = active.length ? "active" : errors.length ? "error" : "idle";

  return (
    <div id="dl-dock" hidden={live.length === 0} data-state={state}>
      <div className="dl-head">
        <button
          ref={barRef}
          className="dl-bar"
          id="dl-bar"
          type="button"
          aria-expanded={expanded}
          aria-controls="dl-panel"
          aria-label={t(expanded ? "jobs.dock.collapse" : "jobs.dock.expand")}
          onClick={() => toggle()}
        >
          <span className="dl-dot" aria-hidden="true" />
          <span className="dl-bar-text">{label}</span>
          <span className="dl-chev" aria-hidden="true">
            {expanded ? "▾" : "▴"}
          </span>
        </button>
        <button
          className="small-btn ghost dl-clear"
          type="button"
          title={t("jobs.dock.clear_title")}
          aria-label={t("jobs.dock.clear_aria")}
          hidden={!(expanded && finished)}
          onClick={clearFinished}
        >
          {t("jobs.dock.clear")}
        </button>
      </div>
      <div
        className={clsx("dl-panel", expanded && "open")}
        id="dl-panel"
        role="log"
        aria-label={t("jobs.dock.background_aria")}
        aria-live="polite"
      >
        <div className="dl-list">
          {list.map((item) => {
            const itemTitle = resolveMessage(item.title);
            const itemName = resolveMessage(item.name);
            const title = itemName && itemName !== itemTitle ? itemTitle ? `${itemTitle} · ${itemName}` : itemName : itemTitle;
            return (
              <div
                key={item.id}
                className={clsx("dl-item", item.removing && "out")}
                role="status"
                data-state={item.status}
              >
                <div className="dl-item-main">
                  <div className="dl-item-title">{title}</div>
                  <StatusLine className="dl-item-sub" kind={(item.status === "done" ? "ok" : item.status === "error" ? "danger" : "info") as StatusKind}>
                    {resolveMessage(item.msg)}
                  </StatusLine>
                  <div className="dl-bar-track">
                    <div
                      className="dl-bar-fill"
                      style={{
                        width: `${item.percent == null ? 0 : Math.max(0, Math.min(100, item.percent))}%`,
                      }}
                    />
                  </div>
                </div>
                <button
                  className="dl-item-dismiss ghost iconbtn"
                  type="button"
                  title={t("jobs.dock.dismiss")}
                  aria-label={t("jobs.dock.dismiss_item", { title: itemTitle })}
                  onClick={(e) => {
                    e.stopPropagation();
                    dismiss(item.id);
                  }}
                >
                  <Icon name="x" />
                </button>
              </div>
            );
          })}
        </div>
        <div className="dl-empty" hidden={live.length > 0}>
          {t("jobs.dock.empty")}
        </div>
      </div>
    </div>
  );
}
