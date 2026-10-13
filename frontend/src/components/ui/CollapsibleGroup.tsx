/* Сворачиваемая секция (reports.js/library.js): caret + aria-expanded. */
import { useState, type ReactNode } from "react";
import clsx from "clsx";

export function CollapsibleGroup({
  title,
  open = true,
  className = "",
  children,
}: {
  title: string;
  open?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const [show, setShow] = useState(open);
  return (
    <div className={clsx("group", className)}>
      <button className="group-head" type="button" aria-expanded={show} onClick={() => setShow((v) => !v)}>
        <span className="caret">{show ? "▾" : "▸"}</span>
        <span>{title}</span>
      </button>
      {show ? <div className="group-body">{children}</div> : null}
    </div>
  );
}
