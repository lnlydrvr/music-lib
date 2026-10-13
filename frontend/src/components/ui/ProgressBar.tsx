import { resolveMessage, type RenderableMessage } from "../../i18n/messages";
import { useTranslation } from "react-i18next";

/* Полоса прогресса операции (контролируемая; была pb.set(pct, msg)). */

export function ProgressBar({ pct, msg }: { pct: number; msg?: RenderableMessage }) {
  const { t } = useTranslation();
  const v = Math.max(0, Math.min(100, pct));
  return (
    <div>
      <div
        className="progress"
        role="progressbar"
        aria-label={t("common.progress_aria")}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(v)}
      >
        <div style={{ width: `${v}%` }} />
      </div>
      <div className="progress-label" aria-live="polite">
        {msg === undefined ? "" : resolveMessage(msg)}
      </div>
    </div>
  );
}
