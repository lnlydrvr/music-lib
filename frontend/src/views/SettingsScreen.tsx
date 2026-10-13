/* Настройки: компактные карточки 2-колоночной сеткой, sticky-шапка с dirty. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { get, put } from "../lib/api";
import { toast } from "../lib/toast";
import { startJob } from "../lib/jobs";
import { getDialogs } from "../components/dialogs/DialogProvider";
import { SegControl } from "../components/ui/SegControl";
import { ProgressBar } from "../components/ui/ProgressBar";
import { Card, Field, openBrowse, SwitchRow } from "./settings/parts";
import { SettingsSkeleton } from "./settings/SettingsSkeleton";
import { YtmCard } from "./settings/YtmCard";
import { changeLanguage, LOCALE_INFO, type Locale } from "../i18n";
import type { RenderableMessage } from "../i18n/messages";
import { asRenderableMessage, resolveMessage } from "../i18n/messages";

interface SettingsData {
  output_dir: string;
  default_format: string;
  default_quality: number;
  source_format: string;
  source_formats?: string[];
  shazam_file: string;
  primuse_sidecar: boolean;
  youtube_browser: string;
  youtube_browsers: string[];
  youtube_cookies_file: string;
  youtube_cookies_set: boolean;
  ytmusic_no_clips: boolean;
  ytm_feedback_action: string;
  search_source: string;
  name_translit: string;
  metadata_sources: string[];
  metadata_sources_order?: string[];
  metadata_sources_available: string[];
  formats: string[];
  language: Locale | null;
}

/* Строка источника: dnd-kit-сортировка, драг только за хэндл ⋮⋮ —
   listeners на всей строке сломали бы клик по чекбоксу. */
function SourceRow({ id, on, onToggle }: { id: string; on: boolean; onToggle: (id: string, v: boolean) => void }) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  return (
    <label
      ref={setNodeRef}
      className={clsx("set-switch-row src-row", isDragging && "dragging")}
      style={{ transform: CSS.Translate.toString(transform), transition }}
    >
      <span className="src-left">
        <span className="src-handle" title={t("settings.sources.drag_title")} {...attributes} {...listeners}>
          ⋮⋮
        </span>
        <span className="src-name">{id}</span>
      </span>
      <span className="switch">
        <input
          type="checkbox"
          className="switch-input"
          checked={on}
          onChange={(e) => onToggle(id, e.target.checked)}
        />
        <span className="switch-track" />
      </span>
    </label>
  );
}

export default function SettingsScreen() {
  const { t, i18n } = useTranslation();
  const [s, setS] = useState<SettingsData | null>(null);
  const [loadError, setLoadError] = useState<RenderableMessage>("");
  /* Форма — один объект: dirty считается снапшотом JSON (как в старом). */
  const [form, setForm] = useState<SettingsData | null>(null);
  const [sourceOrder, setSourceOrder] = useState<string[]>([]);
  const [sourcesOn, setSourcesOn] = useState<Set<string>>(new Set());
  const [primuseOut, setPrimuseOut] = useState<{ pct: number; msg: RenderableMessage } | null>(null);
  /* Снапшот сохранённого состояния: «» — ещё не загружено. */
  const [savedSnap, setSavedSnap] = useState("");
  // Language saves must preserve selection order: a delayed earlier request must
  // not overwrite the user's later, already-applied choice on the server.
  const languageSaveQueue = useRef<Promise<unknown>>(Promise.resolve());
  /* Клик/чекбокс ≠ драг: активация только после смещения на 5px. */
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function buildSnapshot(f: SettingsData, order: string[], on: Set<string>): string {
    return JSON.stringify({ ...f, sources: [order, [...on]] });
  }

  useEffect(() => {
    get<SettingsData>("/api/settings")
      .then((data) => {
        setS(data);
        setForm(data);
        const order =
          Array.isArray(data.metadata_sources_order) && data.metadata_sources_order.length
            ? [...data.metadata_sources_order]
            : [...(data.metadata_sources_available || [])];
        setSourceOrder(order);
        setSourcesOn(new Set(data.metadata_sources));
        setSavedSnap(buildSnapshot(data, order, new Set(data.metadata_sources)));
      })
      .catch((e) => setLoadError(asRenderableMessage(e)));
  }, []);

  const snapshot = useMemo(
    () => (form ? buildSnapshot(form, sourceOrder, sourcesOn) : ""),
    [form, sourceOrder, sourcesOn],
  );
  const dirty = savedSnap !== "" && snapshot !== savedSnap;

  const patch = useCallback((p: Partial<SettingsData>) => {
    setForm((f) => (f ? { ...f, ...p } : f));
  }, []);

  const save = useCallback(async () => {
    if (!form) return;
    try {
      const payload = {
        output_dir: form.output_dir.trim(),
        default_format: form.default_format,
        source_format: form.source_format,
        default_quality: Number(form.default_quality),
        shazam_file: form.shazam_file.trim(),
        primuse_sidecar: form.primuse_sidecar,
        name_translit: form.name_translit,
        ytm_feedback_action: form.ytm_feedback_action,
        search_source: form.search_source,
        youtube_browser: form.youtube_browser,
        ytmusic_no_clips: form.ytmusic_no_clips,
        metadata_sources: sourceOrder.filter((id) => sourcesOn.has(id)),
        metadata_sources_order: [...sourceOrder],
      };
      const res = await put<{ migrated_shazam?: number }>("/api/settings", payload);
      setSavedSnap(snapshot);
      if (res && res.migrated_shazam) {
        toast(t("settings.shazam.migrated", { count: res.migrated_shazam }));
      }
      toast(t("settings.saved"));
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }, [form, sourceOrder, sourcesOn, snapshot, t]);

  const browse = useCallback(async (key: "output_dir" | "shazam_file", kind: "folder" | "file") => {
    const picked = await openBrowse(form?.[key] || "", kind);
    if (picked) patch({ [key]: picked } as Partial<SettingsData>);
  }, [form, patch]);

  const setLanguage = useCallback(async (locale: Locale) => {
    await changeLanguage(locale);
    const save = languageSaveQueue.current.then(() => put("/api/settings", { language: locale }));
    languageSaveQueue.current = save.catch(() => undefined);
    try {
      await save;
    } catch {
      toast(i18n.t("settings.language.save_failed"), "error");
    }
  }, [i18n]);

  const primuseBackfill = useCallback(async () => {
    setPrimuseOut({ pct: 0, msg: "" });
    try {
      const res = await startJob<{ wrote_lrc?: number; wrote_cover?: number; skipped?: number }>(
        "/api/primuse/backfill",
        {},
        { onProgress: (d) => setPrimuseOut({ pct: d.percent ?? 0, msg: d.message ?? d.msg ?? "" }) },
      );
      setPrimuseOut({
        pct: 100,
        msg: { code: "settings.primuse.backfill_summary", params: { lyrics: res.wrote_lrc || 0, covers: res.wrote_cover || 0, skipped: res.skipped || 0 } },
      });
      toast(t("settings.primuse.backfill_done"));
    } catch (e) {
      setPrimuseOut({ pct: 0, msg: "" });
      toast(asRenderableMessage(e), "error");
    }
  }, [t]);

  const primuseCleanup = useCallback(async () => {
    try {
      const prev = await get<{ lrc?: number; covers?: number }>("/api/primuse/cleanup/preview");
      const ok = await getDialogs().confirm(
        t("settings.primuse.cleanup_confirm", { lyrics: prev.lrc || 0, covers: prev.covers || 0 }),
        { defaultOk: false, okTitle: t("settings.delete") },
      );
      if (!ok) return;
      setPrimuseOut({ pct: 0, msg: "" });
      const res = await startJob<{ deleted_lrc?: number; deleted_covers?: number }>(
        "/api/primuse/cleanup",
        {},
        { onProgress: (d) => setPrimuseOut({ pct: d.percent ?? 0, msg: d.message ?? d.msg ?? "" }) },
      );
      setPrimuseOut({ pct: 100, msg: { code: "settings.primuse.cleanup_summary", params: { lyrics: res.deleted_lrc || 0, covers: res.deleted_covers || 0 } } });
      toast(t("settings.primuse.cleanup_done"));
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }, [t]);

  if (loadError) return <div className="panel" style={{ borderColor: "var(--danger)" }}>{resolveMessage(loadError)}</div>;
  /* Форма ещё не читалась: скелетон сетки карточек вместо пустого экрана. */
  if (!s || !form) return <SettingsSkeleton />;

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    setSourceOrder((order) => arrayMove(order, order.indexOf(String(active.id)), order.indexOf(String(over.id))));
  };

  return (
    <>
      <div className="set-head">
        <div>
          <h1 style={{ margin: 0 }}>{t("nav.settings")}</h1>
          <div className="comment" style={{ margin: 0 }}>{t("settings.subtitle")}</div>
        </div>
        <div className="row">
          {dirty ? <span className="set-dirty">●</span> : null}
          <button type="button" disabled={!dirty} onClick={() => void save()}>{t("settings.save")}</button>
        </div>
      </div>

      <div className="set-grid">
        <div className="set-col">
          <Card title={t("settings.language.label")} sub="">
            <label className="set-field">
              <span className="set-label">{t("settings.language.label")}</span>
              <select
                aria-label={t("settings.language.label")}
                value={i18n.resolvedLanguage}
                onChange={(event) => void setLanguage(event.target.value as Locale)}
              >
                {LOCALE_INFO.map(({ code, name }) => <option key={code} value={code}>{name}</option>)}
              </select>
            </label>
          </Card>
          <Card title={t("nav.library")} sub={t("settings.library.subtitle")}>
            <Field label={t("settings.library.directory")}>
              <div className="row set-dirrow">
                <input type="text" value={form.output_dir} onChange={(e) => patch({ output_dir: e.target.value })} />
                <button className="ghost" type="button" onClick={() => void browse("output_dir", "folder")}>{t("settings.browse.action")}</button>
              </div>
            </Field>
            <div className="set-cols3">
              <Field label={t("settings.format.source")} hint={t("settings.format.source_hint")}>
                <select value={form.source_format} onChange={(e) => patch({ source_format: e.target.value })}>
                  {(s.source_formats || ["m4a", "opus"]).map((f) => (
                    <option key={f} value={f}>{f.toUpperCase()}</option>
                  ))}
                </select>
              </Field>
              <Field label={t("settings.format.output")} hint={t("settings.format.output_hint")}>
                <select value={form.default_format} onChange={(e) => patch({ default_format: e.target.value })}>
                  {s.formats.map((f) => (
                    <option key={f} value={f}>{f.toUpperCase()}</option>
                  ))}
                </select>
              </Field>
              <Field label={t("settings.format.quality")}>
                <input
                  type="number"
                  min={1}
                  max={512}
                  value={form.default_quality}
                  onChange={(e) => patch({ default_quality: Number(e.target.value) })}
                />
              </Field>
            </div>
            <Field label={t("settings.names.language")}>
              <SegControl
                options={[
                  ["auto", t("settings.names.auto")],
                  ["cyrillic", t("settings.names.cyrillic")],
                  ["latin", t("settings.names.latin")],
                ]}
                current={form.name_translit as "auto" | "cyrillic" | "latin"}
                onChange={(v) => patch({ name_translit: v })}
              />
            </Field>
            <div className="set-hint">
              {t("settings.names.hint")}
            </div>
          </Card>

          <YtmCard
            noClips={form.ytmusic_no_clips}
            onNoClips={(v) => patch({ ytmusic_no_clips: v })}
            searchSource={form.search_source}
            onSearchSource={(v) => patch({ search_source: v })}
            feedback={form.ytm_feedback_action}
            onFeedback={(v) => patch({ ytm_feedback_action: v })}
            cookies={{
              ytBrowser: form.youtube_browser,
              onYtBrowser: (v) => patch({ youtube_browser: v }),
              browsers: s.youtube_browsers || [],
              set: s.youtube_cookies_set,
              file: s.youtube_cookies_file,
              onCookiesSaved: (file) => setS((cur) => (cur ? { ...cur, youtube_cookies_set: true, youtube_cookies_file: file } : cur)),
              onCookiesDeleted: () => setS((cur) => (cur ? { ...cur, youtube_cookies_set: false } : cur)),
            }}
          />
        </div>

        <div className="set-col">
          <Card title={t("settings.sources.title")} sub={t("settings.sources.subtitle")}>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
              <div className="set-sources">
                <SortableContext items={sourceOrder} strategy={verticalListSortingStrategy}>
                  {sourceOrder.map((id) => (
                    <SourceRow
                      key={id}
                      id={id}
                      on={sourcesOn.has(id)}
                      onToggle={(src, v) =>
                        setSourcesOn((cur) => {
                          const next = new Set(cur);
                          if (v) next.add(src);
                          else next.delete(src);
                          return next;
                        })
                      }
                    />
                  ))}
                </SortableContext>
              </div>
            </DndContext>
            <div className="set-hint">
              {t("settings.sources.order_hint")}
            </div>
          </Card>

          <Card title={t("settings.files.title")} sub="Shazam">
            <Field label={t("settings.files.shazam")} hint={t("settings.files.shazam_hint")}>
              <div className="row set-dirrow">
                <input type="text" value={form.shazam_file} onChange={(e) => patch({ shazam_file: e.target.value })} />
                <button className="ghost" type="button" onClick={() => void browse("shazam_file", "file")}>{t("settings.browse.action")}</button>
              </div>
            </Field>
          </Card>

          <Card title="Primuse" sub={t("settings.primuse.subtitle")}>
            <SwitchRow
              text={t("settings.primuse.save")}
              checked={form.primuse_sidecar}
              onChange={(v) => patch({ primuse_sidecar: v })}
            />
            <div className="row" style={{ marginTop: 8 }}>
              <button className="ghost small-btn" type="button" onClick={() => void primuseBackfill()}>
                {t("settings.primuse.create_all")}
              </button>
              <button className="ghost small-btn" type="button" onClick={() => void primuseCleanup()}>
                {t("settings.primuse.delete_all")}
              </button>
            </div>
            {primuseOut != null ? <ProgressBar pct={primuseOut.pct} msg={primuseOut.msg} /> : null}
          </Card>
        </div>
      </div>
    </>
  );
}
