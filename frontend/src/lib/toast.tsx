/* Toast-обёртка над Sonner с семантикой старого components.js:
   error — 5000 мс; обычный длиннее 60 символов — 6500, иначе 3200;
   toastEx — заголовок/тело/undo-кнопка. Карточка рендерит старые
   классы .toast/.toast-title/.toast-body (визуальный паритет). */
import { toast as sonnerToast, Toaster as SonnerToaster } from "sonner";
import { resolveMessage, type RenderableMessage } from "../i18n/messages";
import { useTranslation } from "react-i18next";

export type ToastType = "" | "error" | "warn";

export interface ToastExOptions {
  title?: RenderableMessage;
  body?: RenderableMessage;
  type?: ToastType;
  undoLabel?: RenderableMessage;
  onUndo?: () => void;
  timeout?: number;
}

function durationMs(o: ToastExOptions): number {
  if (o.timeout) return o.timeout;
  if (o.type === "error") return 5000;
  return resolveMessage(o.title ?? "").length + resolveMessage(o.body ?? "").length > 60 ? 6500 : 3200;
}

function ToastCard({ o, t }: { o: ToastExOptions; t: string | number }) {
  const { t: translate } = useTranslation();
  const type = o.type || "";
  return (
    <div className={`toast ${type}`.trim()} role={type === "error" ? "alert" : "status"}>
      {o.title ? <div className="toast-title">{resolveMessage(o.title, translate)}</div> : null}
      {o.body ? <div className="toast-body">{resolveMessage(o.body, translate)}</div> : null}
      {o.undoLabel && o.onUndo ? (
        <button
          className="small-btn ghost toast-undo"
          type="button"
          onClick={() => {
            sonnerToast.dismiss(t);
            try {
              o.onUndo!();
            } catch {
              /* ignore */
            }
          }}
        >
          {resolveMessage(o.undoLabel, translate)}
        </button>
      ) : null}
    </div>
  );
}

export function toastEx(o: ToastExOptions = {}): string | number {
  return sonnerToast.custom((t) => <ToastCard o={o} t={t} />, { duration: durationMs(o) });
}

export function toast(message: RenderableMessage, type: ToastType = ""): string | number {
  return toastEx({ body: message, type });
}

/* Размещение как у старого #toast-root: правый нижний угол, z-index в ui.css. */
export function AppToaster() {
  return <SonnerToaster position="bottom-right" offset="18px" gap={8} toastOptions={{ unstyled: true }} />;
}
