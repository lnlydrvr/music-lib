/* Ядро редактора трека: поля из TAG_FIELDS, чипы-подсказки, Picard-diff
   «было → станет», превью обложки, выбор записи источника. Контракт — как у
   старого createTrackEditor: {tags, save, isDirty, records, selectRecord,
   applyAlbumFallback, markDirty, coverChecked}. */
import {
  useEffect,
  useId,
  useImperativeHandle,
  useMemo,
  useReducer,
  useRef,
  useState,
  type Ref,
} from "react";
import clsx from "clsx";
import { get, post, coverUrl } from "../../lib/api";
import { toast } from "../../lib/toast";
import { wordDiff } from "../../lib/diff";
import { renderDiffParts } from "../../lib/diff.tsx";
import { Spinner } from "../../components/ui/Spinner";
import {
  TAG_FIELDS,
  TAG_FIELD_LIST,
  providerFieldValue,
  validateTagField,
  type ProviderRecord,
  type TagValues,
} from "../../lib/tags";
import { useMetaSources, type MetaResponse } from "./useMetaSources";
import { asRenderableMessage, resolveEditorGroupLabel, resolveEditorValidation, resolveFieldLabel, resolveMessage, type RenderableMessage } from "../../i18n/messages";
import { useTranslation } from "react-i18next";

/* Теги трека с бэкенда: строковые поля + служебные флаги (has_cover и т.п.). */
export interface TrackTags {
  title?: string;
  artist?: string;
  has_cover?: boolean;
  [key: string]: unknown;
}

/* Запись источника с маркером альбомного фолбэка (клон «Теги альбома»). */
export type EditorRecord = ProviderRecord & { __album?: boolean };

export interface TrackEditorHandle {
  tags: () => TrackTags | null;
  save: (opts?: { notify?: boolean }) => Promise<TrackTags | false>;
  isDirty: () => boolean;
  records: () => EditorRecord[] | null;
  selectedRecord: () => EditorRecord | null;
  selectRecord: (rec: EditorRecord) => void;
  applyAlbumFallback: (rec: ProviderRecord) => void;
  markDirty: () => void;
  coverChecked: () => boolean;
}

export interface TrackEditorProps {
  path: string;
  thumbnailUrl?: string;
  /* Готовые записи источников — запросов не будет. */
  records?: EditorRecord[] | null;
  /* Теги трека; без них — GET /api/tags. */
  current?: TrackTags | null;
  autoFetch?: boolean;
  metaPromise?: Promise<MetaResponse> | null;
  onSaved?: (tags: TrackTags) => void;
  onDirty?: (dirty: boolean) => void;
}

interface EditorState {
  ready: boolean;
  loadError: RenderableMessage;
  tags: TrackTags | null;
  initial: TagValues;
  values: TagValues;
  errors: Record<string, RenderableMessage>;
  fallbacks: EditorRecord[];
  selected: EditorRecord | null;
  applyCover: boolean;
  dirty: boolean;
}

type Action =
  | { type: "tags_loaded"; tags: TrackTags }
  | { type: "tags_error"; message: RenderableMessage }
  | { type: "set_field"; field: string; value: string }
  | { type: "restore_field"; field: string }
  | { type: "select"; rec: EditorRecord }
  | { type: "album_fallback"; rec: ProviderRecord }
  | { type: "cover_checked"; value: boolean }
  | { type: "mark_dirty" }
  | { type: "save_ok"; fields: TagValues; updated: TrackTags }
  | { type: "field_errors"; errors: Record<string, RenderableMessage> };

function fieldValues(tags: TrackTags | null | undefined): TagValues {
  const out: TagValues = {};
  TAG_FIELD_LIST.forEach(([f]) => {
    out[f] = String(tags?.[f] || "");
  });
  return out;
}

/* Подстановка выбранной записи: значение источника, при отсутствии поля —
   из файла. Меняются только отличающиеся поля (как dispatchEvent в старом). */
function applyRecord(state: EditorState, rec: EditorRecord): Partial<EditorState> {
  const values = { ...state.values };
  const errors = { ...state.errors };
  let changed = false;
  TAG_FIELD_LIST.forEach(([f]) => {
    const next = providerFieldValue(rec, f) || state.initial[f];
    if ((values[f] || "").trim() !== next) {
      values[f] = next;
      delete errors[f];
      changed = true;
    }
  });
  return changed ? { values, errors, dirty: true } : {};
}

function reducer(state: EditorState, action: Action): EditorState {
  switch (action.type) {
    case "tags_loaded": {
      const initial = fieldValues(action.tags);
      const next: EditorState = {
        ...state,
        ready: true,
        tags: action.tags,
        initial,
        values: initial,
      };
      // Гонка batch: запись выбрана до загрузки тегов — применяем сейчас.
      return state.selected ? { ...next, ...applyRecord(next, state.selected) } : next;
    }
    case "tags_error":
      return { ...state, ready: true, loadError: action.message };
    case "set_field": {
      const errors = { ...state.errors };
      delete errors[action.field];
      return {
        ...state,
        values: { ...state.values, [action.field]: action.value },
        errors,
        dirty: true,
      };
    }
    case "restore_field": {
      const errors = { ...state.errors };
      delete errors[action.field];
      return {
        ...state,
        values: { ...state.values, [action.field]: state.initial[action.field] },
        errors,
        dirty: true,
      };
    }
    case "select":
      return { ...state, selected: action.rec, ...applyRecord(state, action.rec) };
    case "album_fallback": {
      // Клон с пустыми трековыми полями: applyRecord вернёт их к значениям файла.
      const clone: EditorRecord = {
        ...action.rec,
        title: "",
        artist: "",
        track_number: "",
        __album: true,
      };
      return { ...state, fallbacks: [...state.fallbacks, clone], selected: clone, ...applyRecord(state, clone) };
    }
    case "cover_checked":
      return { ...state, applyCover: action.value, dirty: true };
    case "mark_dirty":
      return state.dirty ? state : { ...state, dirty: true };
    case "save_ok":
      return {
        ...state,
        tags: action.updated,
        initial: action.fields,
        values: action.fields,
        errors: {},
        dirty: false,
      };
    case "field_errors":
      return { ...state, errors: { ...state.errors, ...action.errors } };
  }
}

function init({ current }: TrackEditorProps): EditorState {
  const initial = fieldValues(current);
  return {
    ready: !!current,
    loadError: "",
    tags: current ?? null,
    initial,
    values: initial,
    errors: {},
    fallbacks: [],
    selected: null,
    applyCover: true,
    dirty: false,
  };
}

export function TrackEditor({ ref, ...props }: TrackEditorProps & { ref?: Ref<TrackEditorHandle> }) {
  const { t } = useTranslation();
  const { path, thumbnailUrl = "", records = null, current = null, autoFetch = true } = props;
  const [state, dispatch] = useReducer(reducer, props, init);
  const uid = useId();
  const [savedCover, setSavedCover] = useState(0);
  const inputRefs = useRef(new Map<string, HTMLInputElement>());

  const meta = useMetaSources(path, thumbnailUrl, {
    enabled: autoFetch && records == null && !props.metaPromise,
    metaPromise: props.metaPromise ?? null,
  });

  /* Полный список записей: базовые (пропс/хук) + клоны фолбэка в конце. */
  const baseRecords = records ?? meta.records;
  const allRecords = useMemo<EditorRecord[] | null>(() => {
    if (baseRecords == null) return null;
    return state.fallbacks.length ? [...baseRecords, ...state.fallbacks] : baseRecords;
  }, [baseRecords, state.fallbacks]);

  /* Свежие значения для imperative-хендла. */
  const stateRef = useRef(state);
  stateRef.current = state;
  const recordsRef = useRef(allRecords);
  recordsRef.current = allRecords;

  /* Теги трека: переданы — сразу, иначе GET /api/tags. */
  useEffect(() => {
    if (current) return;
    let alive = true;
    get<TrackTags>("/api/tags", { path })
      .then((tags) => {
        if (alive) dispatch({ type: "tags_loaded", tags });
      })
      .catch((e: unknown) => {
        if (alive) dispatch({ type: "tags_error", message: asRenderableMessage(e) });
      });
    return () => {
      alive = false;
    };
  }, [current, path]);

  useEffect(() => {
    props.onDirty?.(state.dirty);
  }, [state.dirty, props.onDirty]);

  async function save({ notify = true } = {}): Promise<TrackTags | false> {
    const st = stateRef.current;
    const fields: TagValues = {};
    const errors: Record<string, RenderableMessage> = {};
    let bad = "";
    TAG_FIELD_LIST.forEach(([f]) => {
      fields[f] = (st.values[f] || "").trim();
      const msg = validateTagField(f, fields[f]);
      if (msg) {
        errors[f] = msg;
        if (!bad) bad = f;
      }
    });
    if (bad) {
      dispatch({ type: "field_errors", errors });
      toast({ code: "library.album_detail.invalid_field", params: { field: resolveFieldLabel(bad), message: resolveEditorValidation(errors[bad] as string) } }, "error");
      inputRefs.current.get(bad)?.focus();
      return false;
    }
    const rec = st.selected;
    try {
      const updated = await post<TrackTags>("/api/tags/apply", {
        path,
        fields,
        source: rec ? rec.source : "",
        cover_url: rec ? String(rec.cover_url || "") : "",
        thumbnail_url: thumbnailUrl || "",
        apply_cover: st.applyCover,
      });
      if (notify) toast({ code: "editor.saved" });
      // После сохранения исходные значения = записанные в файл.
      setSavedCover((n) => n + 1);
      dispatch({ type: "save_ok", fields, updated });
      props.onSaved?.(updated);
      return updated;
    } catch (e) {
      const err = e as { fields?: Record<string, RenderableMessage>; message?: string };
      if (err.fields) {
        dispatch({ type: "field_errors", errors: err.fields });
        const firstBad = Object.keys(err.fields).find((f) => inputRefs.current.has(f));
        if (firstBad) inputRefs.current.get(firstBad)?.focus();
      }
      toast(asRenderableMessage(e), "error");
      return false;
    }
  }

  useImperativeHandle(
    ref,
    () => ({
      tags: () => stateRef.current.tags,
      save,
      isDirty: () => stateRef.current.dirty,
      records: () => recordsRef.current,
      selectedRecord: () => stateRef.current.selected,
      selectRecord: (rec) => dispatch({ type: "select", rec }),
      applyAlbumFallback: (rec) => dispatch({ type: "album_fallback", rec }),
      markDirty: () => dispatch({ type: "mark_dirty" }),
      coverChecked: () => stateRef.current.applyCover,
    }),
    [],
  );

  if (state.loadError) {
    return (
      <div className="panel" style={{ borderColor: "var(--danger)" }}>{t("editor.load_error")}: {resolveMessage(state.loadError)}</div>
    );
  }
  if (!state.ready) return <Spinner text={t("editor.loading")} />;

  const rec = state.selected;
  const srcUrl = (rec && rec.cover_url) || thumbnailUrl || "";
  const currentCover = state.tags?.has_cover ? (
    // savedCover: после применения обложки /api/cover меняется — сбрасываем кэш.
    <img key={savedCover} src={coverUrl(path)} alt={t("editor.current_cover_alt")} />
  ) : (
    <div className="lib-nocover" aria-hidden="true">♫</div>
  );

  return (
    <div className="editor-grid">
      <div className="editor-side">
        <div className="editor-side-cover">
          <div className="field-group-title">{t("editor.cover")}</div>
          {srcUrl ? (
            <>
              <div className="cover-flow">
                <div className="cover-current" title={t("editor.current_cover")}>{currentCover}</div>
                <div className="cover-arrow">→</div>
                <div className="cover-applied" title={t("editor.source_cover")}>
                  <img src={srcUrl} loading="lazy" alt={t("editor.source_cover_alt")} />
                </div>
              </div>
              <label className="editor-cover-toggle">
                <input
                  type="checkbox"
                  checked={state.applyCover}
                  onChange={(e) => dispatch({ type: "cover_checked", value: e.target.checked })}
                />
                {t("editor.apply_cover")}
              </label>
            </>
          ) : (
            <>
              <div className="editor-cover">{currentCover}</div>
              <div className="muted">{t("editor.cover_not_found")}</div>
            </>
          )}
        </div>
        <div className="field-group-title" style={{ marginTop: 10 }}>{t("editor.source")}</div>
        <SourceList
          records={allRecords}
          pending={meta.pending}
          order={meta.order}
          selected={rec}
          onSelect={(r) => dispatch({ type: "select", rec: r })}
        />
      </div>
      <div className="editor-fields">
        {TAG_FIELDS.map(({ group, fields }) => (
          <div className="field-group" key={group}>
            <div className="field-group-title">{resolveEditorGroupLabel(group)}</div>
            {fields.map(([field, label]) => {
              const fieldLabel = resolveFieldLabel(field) || label;
              const value = state.values[field] || "";
              const orig = state.initial[field] || "";
              const err = state.errors[field] || "";
              const trimmed = value.trim();
              const showChip = !!orig && orig !== trimmed;
              const showOld = showChip;
              const { oldParts, newParts } = showOld ? wordDiff(orig, trimmed) : { oldParts: [], newParts: [] };
              return (
                <div key={field} className={clsx("field-row", trimmed !== orig && "dirty")}>
                  <label className="field-label" htmlFor={`${uid}-${field}`}>{fieldLabel}</label>
                  <div className={clsx("field-input", !!err && "invalid")}>
                    <input
                      type="text"
                      id={`${uid}-${field}`}
                      value={value}
                      aria-describedby={`${uid}-${field}-err`}
                      aria-invalid={!!err || undefined}
                      ref={(n) => {
                        if (n) inputRefs.current.set(field, n);
                        else inputRefs.current.delete(field);
                      }}
                      onChange={(e) => dispatch({ type: "set_field", field, value: e.target.value })}
                    />
                    {showOld ? (
                      <div className="field-old">
                        <span className="del">{renderDiffParts(oldParts, "old")}</span>
                        {" → "}
                        <span className="add">{renderDiffParts(newParts, "new")}</span>
                      </div>
                    ) : null}
                    <div className="field-error" id={`${uid}-${field}-err`} aria-live="polite">
                       {typeof err === "string" && err.startsWith("api.") ? resolveEditorValidation(err) : resolveMessage(err)}
                    </div>
                  </div>
                  {showChip ? (
                    <button
                      className="cand-chip"
                      type="button"
                      title={t("editor.restore_title")}
                      aria-label={t("editor.restore_aria", { field: fieldLabel })}
                      onClick={() => dispatch({ type: "restore_field", field })}
                    >
                      {orig}
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

/* Список записей источников: группы по источнику в порядке настроек,
   параллельные ответы догружаются по мере поступления. */
function SourceList({
  records,
  pending,
  order,
  selected,
  onSelect,
}: {
  records: EditorRecord[] | null;
  pending: string[];
  order: string[];
  selected: EditorRecord | null;
  onSelect: (rec: EditorRecord) => void;
}) {
  const { t } = useTranslation();
  if (records == null) return <Spinner text={t("editor.searching_sources")} />;
  const bySource = new Map<string, EditorRecord[]>();
  for (const r of records) {
    const arr = bySource.get(r.source);
    if (arr) arr.push(r);
    else bySource.set(r.source, [r]);
  }
  const groups: [string, EditorRecord[]][] = [];
  const seen = new Set<string>();
  order.forEach((s) => {
    const arr = bySource.get(s);
    if (arr) {
      groups.push([s, arr]);
      seen.add(s);
    }
  });
  bySource.forEach((arr, s) => {
    if (!seen.has(s)) groups.push([s, arr]);
  });
  if (!groups.length && !pending.length) {
    return <div className="muted">{t("editor.sources_not_found")}</div>;
  }
  return (
    <div className="src-list">
      {groups.map(([source, arr]) => (
        <div key={source}>
          <div className="src-group">{source}</div>
          {arr.map((r, i) => {
            const cardLabel = r.__album
              ? r.album ? t("editor.album_tags_with_album", { album: r.album }) : t("editor.album_tags")
              : [r.title, r.artist, r.album].filter(Boolean).join(" — ") || t("editor.source_record");
            const active = r === selected;
            return (
              <div
                key={i}
                className={clsx("src-card", active && "active", r.__album && "album-fallback")}
                tabIndex={0}
                role="button"
                aria-pressed={active}
                aria-label={t("editor.select_source", { source: cardLabel })}
                onClick={() => onSelect(r)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(r);
                  }
                }}
              >
                {r.cover_url ? (
                  <img src={r.cover_url} loading="lazy" alt="" />
                ) : (
                  <div className="src-noimg" aria-hidden="true">♫</div>
                )}
                <div className="src-meta">
                  <div className="src-title">{r.__album ? t("editor.album_tags") : r.title || "—"}</div>
                  <div className="src-sub">
                    {[r.artist, r.album, r.year ? `(${r.year})` : ""].filter(Boolean).join(" — ")}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}
      {pending.map((name) => (
        <div key={name} className="src-group muted">{t("editor.searching_in", { source: name })}</div>
      ))}
    </div>
  );
}
