/* «Проблемы библиотеки»: единый отчёт (/api/library/quality), плоский список
   треков, пиллы-категории как фильтры, автофиксы и массовые операции. */
import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { get, post } from "../lib/api";
import { toast } from "../lib/toast";
import { useOps, OpPanels } from "../lib/ops";
import { getDialogs } from "../components/dialogs/DialogProvider";
import { trackBatchEditorDialog, trackEditorDialog } from "../features/editor";
import { Table } from "../components/ui/Table";
import { CollapsibleGroup } from "../components/ui/CollapsibleGroup";
import { QualitySkeleton } from "./QualitySkeleton";
import i18n, { resolveMessage } from "../i18n";
import { asRenderableMessage, resolveQualityLabel, type RenderableMessage } from "../i18n/messages";
import { useTranslation } from "react-i18next";

export function categoryLabel(key: string): string {
  return resolveQualityLabel(key);
}

interface QualityIssue {
  category: string;
  message: RenderableMessage;
  auto_fixable?: boolean;
}

interface QualityChange {
  path: string;
  field: string;
  old?: string;
  new?: string;
}

interface QualityTrack {
  path: string;
  title?: string;
  artist?: string;
  album?: string;
  issues: QualityIssue[];
  changes: QualityChange[];
}

interface QualityReport {
  total: number;
  issues: (QualityIssue & { path?: string })[];
  changes: QualityChange[];
  tracks: QualityTrack[];
}

interface QualityPlan {
  counts?: { changes: number; fixes: number };
  changes: QualityChange[];
  fixes: { action?: string; from: string; to: string }[];
  conflicts: { path: string; message?: RenderableMessage; kind?: string }[];
}

export function renderNormalizationChange(change: QualityChange): string {
  return resolveMessage({
    code: "diagnostics.quality.change",
    params: { field: change.field, old: change.old || "", new: change.new || "" },
    message: `${change.field}: “${change.old || ""}” → “${change.new || ""}”`,
  });
}

/* --- diff «было → станет»: общий префикс/суффикс, подсветка середины --- */

function diffRegion(a: string, b: string) {
  let p = 0;
  const n = Math.min(a.length, b.length);
  while (p < n && a[p] === b[p]) p++;
  let s = 0;
  while (s < n - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++;
  return { p, s };
}

/* Ячейка «Было»/«Станет»: изменённая часть подсвечена (del/add). */
function DiffCell({ v, against, cls }: { v: string; against: string; cls: "del" | "add" }) {
  if (!v) return <span className="muted">—</span>;
  const d = diffRegion(v, against);
  const mid = v.slice(d.p, v.length - d.s);
  return (
    <span style={{ whiteSpace: "pre-wrap" }}>
      «{v.slice(0, d.p)}
      {mid ? <span className={cls}>{mid}</span> : null}
      {v.slice(v.length - d.s)}»
    </span>
  );
}

function isInboxPath(p: string): boolean {
  return p.includes("/Inbox/");
}

function PathCell({ p }: { p: string }) {
  return (
    <span style={{ wordBreak: "break-all" }}>
      {p}
      {isInboxPath(p) ? (
        <span className="tag warn" style={{ marginInlineStart: 6 }}>Inbox</span>
      ) : null}
    </span>
  );
}

export function ChangeTable({ items }: { items: QualityChange[] }) {
  const { t } = useTranslation();
  return (
    <Table headers={[t("quality.screen.field"), t("quality.screen.file"), t("quality.screen.old"), t("quality.screen.new")] }>
      {items.map((c, i) => (
        <tr key={`${c.path}:${c.field}:${i}`}>
          <td><b>{renderNormalizationChange(c)}</b></td>
          <td><PathCell p={c.path} /></td>
          <td><DiffCell v={c.old || ""} against={c.new || ""} cls="del" /></td>
          <td>
            → <DiffCell v={c.new || ""} against={c.old || ""} cls="add" />
          </td>
        </tr>
      ))}
    </Table>
  );
}

/* Подтверждение применения плана: diff + переносы + конфликты. */
function PlanDialogBody({ plan }: { plan: QualityPlan }) {
  const { t } = useTranslation();
  return <>
    {plan.changes.length ? <><h4>{t("quality.screen.tag_changes", { count: plan.changes.length })}</h4><ChangeTable items={plan.changes} /></> : null}
    {plan.fixes.length ? <><h4>{t("quality.screen.files", { count: plan.fixes.length })}</h4><Table headers={[t("quality.screen.action"), t("quality.screen.file"), t("quality.screen.destination")] }>{plan.fixes.map((f, i) => <tr key={i}><td>{f.action === "move" ? t("quality.screen.move") : t("quality.screen.rename")}</td><td><PathCell p={f.from} /></td><td>→ <span style={{ wordBreak: "break-all" }}>{f.to}</span></td></tr>)}</Table></> : null}
    {plan.conflicts.length ? <><h4 style={{ color: "var(--danger)" }}>{t("quality.screen.conflicts", { count: plan.conflicts.length })}</h4><div className="comment">{t("quality.screen.conflicts_hint")}</div><Table headers={[t("quality.screen.file"), t("quality.screen.obstacle")] }>{plan.conflicts.map((c, i) => <tr key={i}><td><PathCell p={c.path} /></td><td className="bad">{c.message ? resolveMessage(c.message) : c.kind}</td></tr>)}</Table></> : null}
  </>;
}

export async function confirmPlanDialog(plan: QualityPlan): Promise<boolean> {
  const total = (plan.counts ? plan.counts.changes + plan.counts.fixes : 0)
    || plan.changes.length + plan.fixes.length;
  const res = await getDialogs().open({
    wide: true,
    title: { code: "quality.screen.apply_title" },
    build: () => <PlanDialogBody plan={plan} />,
    actions: [
      { title: { code: "quality.screen.apply", params: { count: total } }, value: true, ok: true },
      { title: { code: "quality.screen.cancel" }, class: "ghost", value: false, ok: true },
    ],
  });
  return res === true;
}

export default function QualityScreen() {
  const { t } = useTranslation();
  const [includeInbox, setIncludeInbox] = useState(false);
  const [data, setData] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<RenderableMessage>("");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lyricsUpdating, setLyricsUpdating] = useState(false);
  const { ops, start: startOp } = useOps();

  const load = useCallback(async (withInbox = includeInbox) => {
    setLoading(true);
    setError("");
    try {
      const d = await get<QualityReport>("/api/library/quality", withInbox ? { include_inbox: 1 } : undefined);
      setData(d);
      setSelected(new Set());
      setHidden(new Set());
    } catch (e) {
      setError(asRenderableMessage(e));
    }
    setLoading(false);
  }, [includeInbox]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.body.classList.toggle("sel-open", selected.size > 0);
    return () => document.body.classList.remove("sel-open");
  }, [selected.size]);

  const byPath = useMemo(() => new Map((data?.tracks || []).map((t) => [t.path, t])), [data]);
  /* Пиллы-категории считаются по всем issues отчёта. */
  const cats = useMemo(() => {
    const counts: Record<string, number> = {};
    (data?.issues || []).forEach((issue) => {
      counts[issue.category] = (counts[issue.category] || 0) + 1;
    });
    return Object.entries(counts).map(([key, count]) => ({ key, label: categoryLabel(key), count }));
  }, [data, i18n.language]);

  const visible = useMemo(
    () => (data?.tracks || []).filter((t) => t.issues.some((i) => !hidden.has(i.category))),
    [data, hidden],
  );

  const toggleSelect = useCallback((path: string) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  /* Смена фильтра сбрасывает выбор — он живёт в рамках показанного списка. */
  const togglePill = useCallback((key: string) => {
    setSelected(new Set());
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  async function openEditor(track: QualityTrack) {
    const saved = await trackEditorDialog(track.path, "", null, null, { autoFetch: true });
    if (saved) {
      toast(t("editor.saved"));
      await load();
    }
  }

  async function updateLyrics(track: QualityTrack) {
    try {
      const res = await post<{ updated: boolean }>("/api/lyrics/update", { path: track.path });
      toast(res.updated ? t("quality.screen.lyrics_updated") : t("quality.screen.lyrics_missing"), res.updated ? "" : "warn");
      await load();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }

  /* План → подтверждение с diff → применение → перезагрузка отчёта. */
  async function applyToSelected(paths?: string[]) {
    const target = paths || [...selected];
    if (!target.length) {
      toast(t("quality.screen.select_tracks"), "warn");
      return;
    }
    const body = { paths: target };
    let plan: QualityPlan;
    try {
      plan = await post<QualityPlan>("/api/library/quality/plan", body);
    } catch (e) {
      toast(asRenderableMessage(e), "error");
      return;
    }
    if (!plan.counts!.changes && !plan.counts!.fixes) {
      toast(t("quality.screen.no_auto_changes"), "warn");
      return;
    }
    const ok = await confirmPlanDialog(plan);
    if (!ok) return;
    try {
      const res = await post<{ applied: number; skipped: number; conflicts?: number; errors?: number }>(
        "/api/library/quality/apply",
        body,
      );
      const note: string[] = [];
      if (res.conflicts) note.push(t("quality.screen.conflict_note", { count: res.conflicts }));
      if (res.errors) note.push(t("quality.screen.error_note", { count: res.errors }));
      toast(
        t("quality.screen.apply_summary", { applied: res.applied, skipped: res.skipped, notes: note.length ? `, ${note.join(", ")}` : "" }),
        res.errors || res.conflicts ? "warn" : "",
      );
      await load();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }

  async function editorSelected() {
    const paths = [...selected];
    if (!paths.length) {
      toast(t("quality.screen.select_tracks"), "warn");
      return;
    }
    const entries = paths.map((p) => {
      const t = byPath.get(p);
      return { path: p, title: t?.title || p.split("/").pop() || p, artist: t?.artist || "" };
    });
    const saved = await trackBatchEditorDialog(entries);
    const n = saved ? Object.keys(saved).length : 0;
    if (n) {
      toast(t("quality.screen.saved", { count: n }));
      await load();
    }
  }

  async function lyricsSelected() {
    if (lyricsUpdating) return;
    const paths = [...selected];
    if (!paths.length) {
      toast(t("quality.screen.select_tracks"), "warn");
      return;
    }
    const ok = await getDialogs().confirm(t("quality.screen.update_lyrics", { count: paths.length }), { okTitle: t("quality.screen.updating") });
    if (!ok) return;
    const op = startOp();
    setLyricsUpdating(true);
    let updated = 0;
    let missed = 0;
    let errors = 0;
    let completed = 0;
    const next = { value: 0 };
    const worker = async () => {
      while (next.value < paths.length) {
        const path = paths[next.value++];
        try {
          const res = await post<{ updated: boolean }>("/api/lyrics/update", { path });
          if (res.updated) updated += 1;
          else missed += 1;
        } catch {
          errors += 1;
        }
        completed += 1;
        op.set((completed / paths.length) * 100, { code: "quality.lyrics_item_progress", params: { completed, total: paths.length, path: path.split("/").pop() || path } });
      }
    };
    try {
      await Promise.all(Array.from({ length: Math.min(3, paths.length) }, worker));
      op.set(100, t("quality.screen.lyrics_progress", { updated, missed, errors: errors ? `, ${t("quality.screen.error_note", { count: errors })}` : "" }));
      op.set(100, t("quality.screen.refreshing"));
      await load();
    } finally {
      setLyricsUpdating(false);
    }
  }

  const tracksWithChanges = (data?.tracks || []).filter((t) => t.changes.length);
  const allChanges = tracksWithChanges.flatMap((t) => t.changes);
  const allSelected = visible.length > 0 && visible.every((t) => selected.has(t.path));

  return (
    <>
      <h1>{t("quality.screen.title")}</h1>
      <div className="comment">{t("quality.screen.subtitle")}</div>
      <div className="row" style={{ marginBottom: 14 }}>
        <label className="row" style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={includeInbox}
            onChange={(e) => {
              setIncludeInbox(e.target.checked);
              void load(e.target.checked);
            }}
          />
          {t("quality.screen.include_inbox")}
        </label>
        <button type="button" onClick={() => void load()}>{t("quality.refresh")}</button>
      </div>

      <div className={clsx("selbar", selected.size > 0 && "show")} role="toolbar" aria-label={t("quality.selection.toolbar")}>
        <span className="selbar-count muted">{selected.size ? t("quality.screen.selected", { count: selected.size }) : ""}</span>
        <button type="button" onClick={() => void editorSelected()}>{t("quality.screen.editor")}</button>
        <button type="button" onClick={() => void applyToSelected()}>{t("quality.screen.normalize")}</button>
        <button type="button" className="ghost" disabled={lyricsUpdating} onClick={() => void lyricsSelected()}>{t("quality.lyrics.action")}</button>
        <button type="button" className="ghost" onClick={() => setSelected(new Set())}>{t("quality.screen.reset")}</button>
      </div>

      <OpPanels ops={ops} />

      {/* Сканирование — скелетон строк отчёта (та же структура карточек):
          текст-строка оставляла провал высоты перед появлением списка. */}
      {loading ? <QualitySkeleton /> : null}
      {error ? <div className="panel" style={{ borderColor: "var(--danger)" }}>{resolveMessage(error)}</div> : null}
      {!loading && !error && data ? (
        <>
          <div className="row" style={{ marginBottom: 12 }}>
            <span>{t("quality.screen.checked", { count: data.total })}</span>
            <span className={`tag ${data.issues.length ? "bad" : "ok"}`}>{t("quality.screen.problems", { count: data.issues.length })}</span>
            <span className={`tag ${data.changes.length ? "warn" : "ok"}`}>{t("quality.screen.auto_fixes", { count: data.changes.length })}</span>
          </div>
          {!data.issues.length && !data.changes.length ? (
            <div className="panel">{t("quality.screen.none")}</div>
          ) : (
            <>
              {/* Пиллы категорий — фильтры над плоским списком треков. */}
              <div className="pills">
                {cats.map((c) => (
                  <button
                    key={c.key}
                    className={clsx("pill", hidden.has(c.key) && "off")}
                    type="button"
                    aria-pressed={!hidden.has(c.key)}
                    aria-label={hidden.has(c.key) ? t("quality.screen.show_category", { label: c.label }) : t("quality.screen.hide_category", { label: c.label })}
                    onClick={() => togglePill(c.key)}
                  >
                    {t("quality.screen.category_count", { label: c.label, count: c.count })}
                  </button>
                ))}
                {cats.length ? (
                  <button className="pill ghost" type="button" onClick={() => { setSelected(new Set()); setHidden(new Set()); }}>
                    {t("quality.screen.show_all")}
                  </button>
                ) : null}
              </div>

              <div className="quality-results">
                {visible.length ? (
                  <>
                    <div className="row" style={{ marginBottom: 8 }}>
                      <button
                        className="ghost"
                        type="button"
                        onClick={() =>
                          setSelected(() => {
                            if (allSelected) return new Set();
                            return new Set(visible.map((t) => t.path));
                          })
                        }
                      >
                        {allSelected ? t("quality.screen.deselect_all", { count: visible.length }) : t("quality.selection.select_all", { count: visible.length })}
                      </button>
                    </div>
                    <div className="quality-track-list">
                      {visible.map((track) => {
                        const name = track.title || track.path.split("/").pop() || track.path;
                        const canAutoFix = track.changes.length > 0 || track.issues.some((i) => i.auto_fixable);
                        const hasTextProblem = track.issues.some((i) => i.category === "missing");
                        return (
                          <div key={track.path} className={clsx("quality-track", selected.has(track.path) && "chk")} data-path={track.path}>
                            <label className="quality-check">
                              <input
                                type="checkbox"
                                aria-label={t("quality.screen.track_changes", { name })}
                                checked={selected.has(track.path)}
                                onChange={() => toggleSelect(track.path)}
                              />
                            </label>
                            <a href={`#/library?path=${encodeURIComponent(track.path)}`} className="quality-track-info">
                              <div className="quality-track-title">{name}</div>
                              {track.artist || track.album ? (
                                <div className="quality-track-meta">
                                  {[track.artist, track.album].filter(Boolean).join(" · ")}
                                </div>
                              ) : null}
                            </a>
                            <div className="quality-issues">
                              {track.issues.map((issue, i) => (
                                <span key={i} className="quality-issue">
                                    {resolveMessage(issue.message)}
                                </span>
                              ))}
                              {track.changes.length ? (
                                <span className="tag warn" title={t("quality.screen.auto_fixes_title")}>
                                  {t("quality.screen.auto_fixes_badge", { count: track.changes.length })}
                                </span>
                              ) : null}
                            </div>
                            <div className="quality-actions">
                              <button className="ghost" type="button" onClick={() => void openEditor(track)}>{t("quality.screen.editor")}</button>
                              {canAutoFix ? (
                                <button type="button" onClick={() => void applyToSelected([track.path])}>{t("quality.screen.fix")}</button>
                              ) : null}
                              {hasTextProblem ? (
                                <button className="ghost" type="button" onClick={() => void updateLyrics(track)}>{t("quality.lyrics.singular")}</button>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <div className="panel">{t("quality.screen.empty_filter")}</div>
                )}
                {tracksWithChanges.length ? (
                  <CollapsibleGroup title={t("quality.screen.normalization_plan", { count: allChanges.length })} open={false}>
                    <ChangeTable items={allChanges} />
                  </CollapsibleGroup>
                ) : null}
              </div>
            </>
          )}
        </>
      ) : null}
    </>
  );
}
