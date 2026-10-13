/* Визуальный пайплайн этапов: usePipeline хранит состояние (go/reset),
   Pipeline — рендер с data-state и aria-label «метка: ожидает/выполняется». */
import { useCallback, useState } from "react";
import { resolveMessage, type RenderableMessage, type TranslationKey } from "../../i18n/messages";
import { useTranslation } from "react-i18next";

export interface PipeStage {
  id: string;
  label: RenderableMessage;
}

export type PipeNodeState = "pending" | "active" | "done" | "error" | "skip";

const STATE_KEY: Record<PipeNodeState, TranslationKey> = {
  pending: "pipeline.expected",
  active: "pipeline.running",
  done: "pipeline.done",
  error: "pipeline.error",
  skip: "pipeline.skipped",
};

export function Pipeline({
  stages,
  states,
  visible,
}: {
  stages: PipeStage[];
  states: PipeNodeState[];
  visible: boolean;
}) {
  const { t } = useTranslation();
  if (!visible) return null;
  return (
    <div className="pipeline" role="list" aria-label={t("pipeline.aria")}>
      {stages.map((s, i) => (
        <span key={s.id} className="pipe-node" role="listitem" data-id={s.id} data-state={states[i]} aria-label={t("pipeline.stage_aria", { label: resolveMessage(s.label), state: t(STATE_KEY[states[i]]) })}>
          <span className="pipe-row" aria-hidden="true">
            <span className="pipe-conn" />
            <span className="pipe-dot" />
          </span>
          <span className="pipe-label" aria-hidden="true">
            {resolveMessage(s.label)}
          </span>
        </span>
      ))}
    </div>
  );
}

/* go(id, state): этапы до id — done, после — pending (при error — skip). */
export function usePipeline(stages: PipeStage[]) {
  const [states, setStates] = useState<PipeNodeState[]>(() => stages.map(() => "pending"));
  const [visible, setVisible] = useState(false);

  const go = useCallback(
    (id: string, state: "active" | "done" | "error") => {
      setVisible(true);
      const idx = stages.findIndex((s) => s.id === id);
      if (idx < 0) return;
      setStates(() => stages.map((_, i) => {
        if (i < idx) return "done";
        if (i === idx) return state;
        return state === "error" ? "skip" : "pending";
      }));
    },
    [stages],
  );

  const reset = useCallback(() => {
    setStates(stages.map(() => "pending"));
  }, [stages]);

  return { go, reset, node: <Pipeline stages={stages} states={states} visible={visible} /> };
}
