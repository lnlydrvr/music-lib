/* Пустое состояние экрана/списка. */
import type { ReactNode } from "react";

export function EmptyState({
  art = "♫",
  title = "",
  sub = "",
  action = null,
}: {
  art?: string;
  title?: string;
  sub?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="es-art" aria-hidden="true">
        {art}
      </div>
      {title ? <div className="es-title">{title}</div> : null}
      {sub ? <div className="es-sub">{sub}</div> : null}
      {action}
    </div>
  );
}
