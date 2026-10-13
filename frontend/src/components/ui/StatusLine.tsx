import clsx from "clsx";
import type { ReactNode } from "react";

export type StatusKind = "ok" | "warn" | "danger" | "info" | "pending";

const MARKERS: Record<StatusKind, string> = {
  ok: "[ok]",
  warn: "[!]",
  danger: "[!!]",
  info: "[i]",
  pending: "[ ]",
};

export function StatusLine({ kind, children, className }: { kind: StatusKind; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("status-line", `status-line-${kind}`, className)}>
      <span className="status-line-marker" aria-hidden="true">{MARKERS[kind]}</span>
      <span className={className}>{children}</span>
    </span>
  );
}
