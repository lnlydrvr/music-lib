/* Редактор трека: прогрессивная загрузка источников, единый редактор,
   массовое редактирование, метафлоу. Интеграция в экраны — фаза 3. */
export {
  useMetaSources,
  fetchMetaAll,
  fetchMetaBySource,
  clearMetaCache,
  type MetaResponse,
} from "./useMetaSources";
export {
  TrackEditor,
  type EditorRecord,
  type TrackEditorHandle,
  type TrackEditorProps,
  type TrackTags,
} from "./TrackEditor";
export { trackEditorDialog, type TrackEditorOpts } from "./TrackEditorDialog";
export { trackBatchEditorDialog, type BatchEntryInput } from "./BatchEditorDialog";
export { runMetaflow, metaflowStageMessage, type MetaflowStage } from "./runMetaflow";
