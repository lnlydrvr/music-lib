/* Интерактивный метафлоу: источники → применение тегов → LRCLIB.
   Сигнатура — как в старом SPA; шаг LRCLIB перенесён внутрь (раньше его
   вызывали postDownload-флоу экранов) — вызовы молча игнорируют отсутствие
   текста. resolve(success). */
import { post } from "../../lib/api";
import { trackEditorDialog } from "./TrackEditorDialog";
import type { EditorRecord } from "./TrackEditor";
import type { RenderableMessage } from "../../i18n/messages";

export type MetaflowStage = "metadata" | "lyrics";

export function metaflowStageMessage(stage: MetaflowStage): RenderableMessage {
  return stage === "lyrics"
    ? { code: "search.metaflow.lyrics_updating" }
    : { code: "search.metaflow.metadata_searching" };
}

export async function runMetaflow(
  path: string,
  thumbnailUrl = "",
  onStep?: (step: MetaflowStage) => void,
  records?: EditorRecord[] | null,
): Promise<boolean> {
  if (onStep) onStep("metadata");
  const result = await trackEditorDialog(path, thumbnailUrl || "", records || null, null, {
    autoFetch: !records,
  });
  if (onStep) onStep("lyrics");
  try {
    await post("/api/lyrics/update", { path });
  } catch {
    /* нет текста */
  }
  return result != null;
}
