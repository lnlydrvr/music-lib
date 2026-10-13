/* Массовое редактирование: список треков + редактор (master-detail).
   entries: [{path, title, artist}] или [path]. Возвращает {path: tags}
   (null — отмена). Правки живут в редакторах — файл трогаем лишь по «Готово». */
import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { post } from "../../lib/api";
import { toast } from "../../lib/toast";
import { useTranslation } from "react-i18next";
import { pickAlbumRecord, type ProviderRecord } from "../../lib/tags";
import { TrackEditor, type EditorRecord, type TrackEditorHandle, type TrackTags } from "./TrackEditor";
import type { MetaResponse } from "./useMetaSources";

export type BatchEntryInput = string | { path: string; title?: string; artist?: string };

interface NormEntry {
  path: string;
  title: string;
  artist: string;
}

interface BatchApi {
  finish: () => Promise<Record<string, TrackTags> | false>;
}

export async function trackBatchEditorDialog(
  entries: BatchEntryInput[],
): Promise<Record<string, TrackTags> | null> {
  const list: NormEntry[] = entries.map((e) => {
    if (typeof e === "string") {
      return { path: e, title: e.split("/").pop() || e, artist: "" };
    }
    return { path: e.path, title: e.title || e.path.split("/").pop() || e.path, artist: e.artist || "" };
  });
  const apiBox: { current: BatchApi | null } = { current: null };
  const result = await getDialogs().open({
    wide: true,
    cls: "batch",
    title: { code: "editor.batch.title" },
    build: () => <BatchBody list={list} apiBox={apiBox} />,
    actions: [
      // false (ошибка валидации у трека) — остаёмся в модалке на проблемном треке.
      { title: { code: "editor.batch.done" }, onClick: () => apiBox.current?.finish() ?? false },
    ],
  });
  return result && typeof result === "object" ? (result as Record<string, TrackTags>) : null;
}

/* Ожидание смонтированного редактора: ref-callback резолвит промис. */
function waitForEditor(
  editors: Map<string, TrackEditorHandle>,
  waiters: Map<string, (h: TrackEditorHandle) => void>,
  path: string,
): Promise<TrackEditorHandle> {
  const existing = editors.get(path);
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve) => waiters.set(path, resolve));
}

function BatchBody({ list, apiBox }: { list: NormEntry[]; apiBox: { current: BatchApi | null } }) {
  const { t } = useTranslation();
  const [current, setCurrent] = useState(0);
  /* Редакторы монтируются лениво при показе и живут до конца (правки не теряются). */
  const [mounted, setMounted] = useState<string[]>(() => (list.length ? [list[0].path] : []));
  const [recordsByPath, setRecordsByPath] = useState<Record<string, EditorRecord[]>>({});
  const [rowState, setRowState] = useState<Record<string, { dirty?: boolean; saved?: boolean }>>({});
  const [applyLabel, setApplyLabel] = useState<string | null>(null);
  const metaPromises = useRef(new Map<string, Promise<MetaResponse>>());
  const editors = useRef(new Map<string, TrackEditorHandle>());
  const waiters = useRef(new Map<string, (h: TrackEditorHandle) => void>());
  const rowsRef = useRef(new Map<number, HTMLDivElement>());
  const savedMap = useRef(new Map<string, TrackTags>());

  /* Мета следующего трека качается фоном, пока правится текущий. */
  const prefetchMeta = useCallback(
    (i: number) => {
      const item = list[i];
      if (!item || metaPromises.current.has(item.path)) return;
      const p = post<MetaResponse>("/api/fetch/meta", { path: item.path });
      p.catch(() => {});
      metaPromises.current.set(item.path, p);
    },
    [list],
  );

  const show = useCallback(
    (i: number) => {
      const item = list[i];
      if (!item) return;
      setCurrent(i);
      setMounted((m) => (m.includes(item.path) ? m : [...m, item.path]));
      prefetchMeta(i);
      prefetchMeta(i + 1);
    },
    [list, prefetchMeta],
  );

  // Prefetch стартует синхронно при первом рендере (ref-флаг, идемпотентно):
  // эффекты детей (useMetaSources редактора) выполняются раньше эффектов
  // родителя и должны сразу видеть промис в Map.
  const bootstrapped = useRef(false);
  if (!bootstrapped.current) {
    bootstrapped.current = true;
    prefetchMeta(0);
    prefetchMeta(1);
  }

  useEffect(() => {
    apiBox.current = {
      /* Применяем разом все правленные треки; при ошибке валидации
         остаёмся в модалке на проблемном треке. */
      finish: async () => {
        for (let k = 0; k < list.length; k++) {
          const ed = editors.current.get(list[k].path);
          if (!ed || !ed.isDirty()) continue;
          const r = await ed.save({ notify: false });
          if (r === false) {
            show(k);
            return false;
          }
        }
        const n = savedMap.current.size;
        if (n) toast({ code: "editor.batch.saved", params: { count: n } });
        return Object.fromEntries(savedMap.current);
      },
    };
  }, [list, show]);

  const markSaved = useCallback((path: string, tags: TrackTags) => {
    savedMap.current.set(path, tags);
    setRowState((s) => ({ ...s, [path]: { ...s[path], saved: true, dirty: false } }));
  }, []);

  /* «Применить ко всем трекам»: выбранный на текущем треке источник
     применяется ко всем — у кого есть запись этого источника (приоритет у
     совпавшего альбома), получает её целиком; остальным идут только общие
     альбомные поля. */
  const applyAlbumSource = useCallback(async () => {
    const curPath = list[current]?.path || "";
    const chosen = editors.current.get(curPath)?.selectedRecord() || null;
    if (!chosen) {
      toast({ code: "editor.batch.select_source_first" }, "warn");
      return;
    }
    setApplyLabel(t("editor.batch.applying", { index: 1, total: list.length }));
    let applied = 0;
    let failed = 0;
    for (let k = 0; k < list.length; k++) {
      setApplyLabel(t("editor.batch.applying", { index: k + 1, total: list.length }));
      const item = list[k];
      try {
        let recs: ProviderRecord[] | null = null;
        const ed = editors.current.get(item.path);
        if (ed && ed.records() != null) {
          recs = ed.records();
        } else {
          let p = metaPromises.current.get(item.path);
          if (!p) {
            p = post<MetaResponse>("/api/fetch/meta", { path: item.path, sources: [chosen.source] });
            p.catch(() => {});
            metaPromises.current.set(item.path, p);
          }
          recs = (await p).records || [];
        }
        let editor = editors.current.get(item.path) || null;
        if (!editor) {
          // Монтируем редактор с готовыми записями — autoFetch не нужен.
          setMounted((m) => (m.includes(item.path) ? m : [...m, item.path]));
          setRecordsByPath((r) => ({ ...r, [item.path]: recs as EditorRecord[] }));
          editor = await waitForEditor(editors.current, waiters.current, item.path);
        }
        const match = pickAlbumRecord(editor.records(), chosen);
        if (match) editor.selectRecord(match);
        else editor.applyAlbumFallback(chosen);
        // Обложка тоже должна применяться: трек без текстовых изменений
        // не «dirty» и «Готово» его пропустил бы — помечаем принудительно.
        if (chosen.cover_url && editor.coverChecked()) editor.markDirty();
        applied += 1;
      } catch {
        failed += 1;
      }
    }
    setApplyLabel(null);
    toast({ code: "editor.batch.applied", params: { applied, failed } }, failed ? "warn" : "");
  }, [current, list, t]);

  return (
    <div className="batch-grid">
      <div className="batch-side">
        <div className="field-group-title">{t("editor.batch.tracks", { count: list.length })}</div>
        <button
          className="ghost batch-album-btn"
          type="button"
          title={t("editor.batch.apply_source_title")}
          aria-label={t("editor.batch.apply_source_aria")}
          disabled={applyLabel != null}
          onClick={() => void applyAlbumSource()}
        >
          {applyLabel ?? t("editor.batch.apply_all")}
        </button>
        <div className="batch-list" role="listbox" aria-label={t("editor.batch.list_aria")}>
          {list.map((item, i) => {
            const st = rowState[item.path] || {};
            const base = `${item.title}${item.artist ? ` — ${item.artist}` : ""}`;
            return (
              <div
                key={item.path}
                ref={(n) => {
                  if (n) rowsRef.current.set(i, n);
                  else rowsRef.current.delete(i);
                }}
                className={clsx("batch-item", i === current && "active", st.dirty && "dirty", st.saved && "saved")}
                tabIndex={0}
                role="option"
                aria-selected={i === current}
                aria-label={st.dirty ? t("editor.batch.unsaved_aria", { title: base }) : base}
                onClick={() => show(i)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    show(i);
                  } else if (e.key === "ArrowDown" || e.key === "ArrowRight") {
                    e.preventDefault();
                    const n = Math.min(list.length - 1, i + 1);
                    rowsRef.current.get(n)?.focus();
                    show(n);
                  } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    const n = Math.max(0, i - 1);
                    rowsRef.current.get(n)?.focus();
                    show(n);
                  }
                }}
              >
                <div className="batch-title">{item.title}</div>
                <div className="batch-sub">{item.artist}</div>
                <div className="batch-status" aria-hidden="true" />
              </div>
            );
          })}
        </div>
      </div>
      <div className="batch-host" aria-live="polite">
        {mounted.map((path) => {
          const i = list.findIndex((e) => e.path === path);
          const recs = recordsByPath[path] ?? null;
          return (
            <div key={path} data-path={path} style={{ display: i === current ? "" : "none" }}>
              <TrackEditor
                ref={(h) => {
                  if (!h) return;
                  editors.current.set(path, h);
                  const w = waiters.current.get(path);
                  if (w) {
                    waiters.current.delete(path);
                    w(h);
                  }
                }}
                path={path}
                records={recs}
                autoFetch={!recs}
                metaPromise={recs ? null : (metaPromises.current.get(path) ?? null)}
                onSaved={(tags) => markSaved(path, tags)}
                onDirty={(d) =>
                  setRowState((s) => (s[path]?.dirty === d ? s : { ...s, [path]: { ...s[path], dirty: d } }))
                }
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
