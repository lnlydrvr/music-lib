/* Локальные прогресс-панели операций (pipeline + progressbar): состояние
   держит useOps, панель рендерится сверху списка (аналог box.prepend). */
import { useCallback, useRef, useState } from "react";
import { Pipeline, type PipeNodeState, type PipeStage } from "../components/ui/Pipeline";
import { ProgressBar } from "../components/ui/ProgressBar";
import { resolveMessage, type RenderableMessage } from "../i18n/messages";
import { useTranslation } from "react-i18next";

export interface OpState {
  id: number;
  stages: PipeStage[];
  states: PipeNodeState[];
  visible: boolean;
  pct: number;
  msg: RenderableMessage;
}

export interface OpHandle {
  go: (stageId: string, state: "active" | "done" | "error") => void;
  set: (pct: number, msg?: RenderableMessage) => void;
}

export function useOps() {
  const [ops, setOps] = useState<OpState[]>([]);
  const seq = useRef(0);

  /* Стабильная ссылка: эффекты вьюх зависят от неё (иначе цикл ререндеров). */
  const start = useCallback((stages: PipeStage[] = []): OpHandle => {
    const id = ++seq.current;
    setOps((arr) => [
      { id, stages, states: stages.map(() => "pending"), visible: false, pct: 0, msg: "" },
      ...arr,
    ]);
    const patch = (fn: (op: OpState) => OpState) =>
      setOps((arr) => arr.map((o) => (o.id === id ? fn(o) : o)));
    return {
      go: (stageId, state) =>
        patch((o) => {
          const idx = o.stages.findIndex((s) => s.id === stageId);
          if (idx < 0) return o;
          return {
            ...o,
            visible: true,
            states: o.stages.map((_, i) => {
              if (i < idx) return "done";
              if (i === idx) return state;
              return state === "error" ? "skip" : "pending";
            }),
          };
        }),
      set: (pct, msg) => patch((o) => ({ ...o, visible: true, pct, msg: msg ?? o.msg })),
    };
  }, []);

  return { ops, start };
}

export function OpPanels({ ops }: { ops: OpState[] }) {
  useTranslation();
  return (
    <>
      {ops.map((op) => (
        <div key={op.id} className="panel">
          {op.stages.length ? <Pipeline stages={op.stages} states={op.states} visible={op.visible} /> : null}
          <ProgressBar pct={op.pct} msg={resolveMessage(op.msg)} />
        </div>
      ))}
    </>
  );
}
