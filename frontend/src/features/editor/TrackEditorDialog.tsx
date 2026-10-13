/* Единый редактор трека в модалке (Promise-API поверх DialogProvider).
   Возвращает обновлённые теги или null. Теги грузятся до открытия диалога —
   заголовок известен сразу, как в старом SPA. */
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { get } from "../../lib/api";
import { toast } from "../../lib/toast";
import { TrackEditor, type EditorRecord, type TrackEditorHandle, type TrackTags } from "./TrackEditor";
import type { MetaResponse } from "./useMetaSources";
import { asRenderableMessage } from "../../i18n/messages";

export interface TrackEditorOpts {
  autoFetch?: boolean;
  onSaved?: (tags: TrackTags) => void;
  onDirty?: (dirty: boolean) => void;
  metaPromise?: Promise<MetaResponse> | null;
}

export async function trackEditorDialog(
  path: string,
  thumbnailUrl = "",
  records: EditorRecord[] | null = null,
  current: TrackTags | null = null,
  opts: TrackEditorOpts = {},
): Promise<TrackTags | null> {
  let tags = current;
  if (!tags) {
    try {
      tags = await get<TrackTags>("/api/tags", { path });
    } catch (e) {
      toast(asRenderableMessage(e), "error");
      return null;
    }
  }
  const editorRef: { current: TrackEditorHandle | null } = { current: null };
  const result = await getDialogs().open({
    wide: true,
    title: { code: "editor.dialog.title", params: { title: tags.title || { code: "editor.dialog.untitled" } } },
    build: () => (
      <TrackEditor
        ref={(h) => {
          editorRef.current = h;
        }}
        path={path}
        thumbnailUrl={thumbnailUrl}
        records={records}
        current={tags}
        autoFetch={opts.autoFetch ?? true}
        metaPromise={opts.metaPromise ?? null}
        onSaved={opts.onSaved}
        onDirty={opts.onDirty}
      />
    ),
    actions: [
      // false (ошибка валидации/записи) — модалка остаётся открытой.
      { title: { code: "editor.dialog.save" }, onClick: () => editorRef.current?.save() ?? false },
      { title: { code: "editor.dialog.cancel" }, class: "ghost", value: null, ok: true },
    ],
  });
  return result && typeof result === "object" ? (result as TrackTags) : null;
}
