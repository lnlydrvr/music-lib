/* Рендер частей wordDiff: удаления/вставки подсвечиваются wd-del/wd-add. */
import type { DiffPart } from "./diff";

export function renderDiffParts(parts: DiffPart[], cls: "old" | "new") {
  return parts.map((p, i) =>
    p.del || p.add ? (
      <span key={i} className={cls === "old" ? "wd-del" : "wd-add"}>
        {p.t}
      </span>
    ) : (
      <span key={i}>{p.t}</span>
    ),
  );
}
