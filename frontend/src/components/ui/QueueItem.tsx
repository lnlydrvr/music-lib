/* Живая очередь задач (классы .queue-item/.q-*): состояние держит useQueue,
   QueueItem — только рендер. */
import { useCallback, useRef, useState } from "react";
import { toastEx } from "../../lib/toast";
import type { RenderableMessage } from "../../i18n/messages";
import { resolveMessage } from "../../i18n/messages";
import { StatusLine, type StatusKind } from "./StatusLine";
import { useTranslation } from "react-i18next";

export type QueueState = "active" | "done" | "error";

export interface QueueEntry {
  id: number;
  title: RenderableMessage;
  sub: RenderableMessage;
  pct: number | null;
  state: QueueState;
}

export function QueueItem({ entry }: { entry: QueueEntry }) {
  useTranslation();
  const w = entry.pct == null ? 0 : Math.max(0, Math.min(100, entry.pct));
  const kind: StatusKind = entry.state === "done" ? "ok" : entry.state === "error" ? "danger" : "info";
  return (
    <div className="queue-item" data-state={entry.state} role="status">
      <div className="q-info">
        <div className="q-title">{resolveMessage(entry.title)}</div>
        <div className="q-sub"><StatusLine kind={kind}>{resolveMessage(entry.sub)}</StatusLine></div>
        <div className="q-bar">
          <div className="q-fill" style={{ width: `${w}%` }} />
        </div>
      </div>
    </div>
  );
}

/* Очередь с set/done/error/dismiss (+undo-тост), как императивный queueItem. */
export function useQueue() {
  const [items, setItems] = useState<QueueEntry[]>([]);
  const seq = useRef(0);

  const add = useCallback((title: RenderableMessage, sub: RenderableMessage = "") => {
    const id = ++seq.current;
    setItems((arr) => [...arr, { id, title, sub, pct: null, state: "active" }]);
    return id;
  }, []);

  const update = useCallback((id: number, patch: Partial<QueueEntry>) => {
    setItems((arr) => arr.map((i) => (i.id === id ? { ...i, ...patch } : i)));
  }, []);

  const set = useCallback(
    (id: number, pct: number | null, text?: RenderableMessage) => {
      setItems((arr) =>
        arr.map((i) =>
          i.id === id
            ? {
                ...i,
                pct: pct == null ? i.pct : pct,
                sub: text ?? i.sub,
              }
            : i,
        ),
      );
    },
    [],
  );

  const done = useCallback(
    (id: number, text?: RenderableMessage) => update(id, { state: "done", pct: 100, sub: text ?? { code: "queue.done" } }),
    [update],
  );

  const error = useCallback(
    (id: number, text?: RenderableMessage) => update(id, { state: "error", pct: 0, sub: text ?? { code: "queue.error" } }),
    [update],
  );

  const dismiss = useCallback((id: number) => {
    setItems((arr) => {
      const idx = arr.findIndex((i) => i.id === id);
      if (idx < 0) return arr;
      const entry = arr[idx];
      // Undo возвращает элемент на прежнее место списка.
      toastEx({
        title: { code: "queue.dismissed" },
        body: entry.title,
        undoLabel: { code: "queue.undo" },
        onUndo: () => {
          setItems((cur) => {
            const without = cur.filter((i) => i.id !== id);
            const at = Math.min(idx, without.length);
            return [...without.slice(0, at), entry, ...without.slice(at)];
          });
        },
      });
      return arr.filter((i) => i.id !== id);
    });
  }, []);

  return { items, add, set, done, error, dismiss };
}
