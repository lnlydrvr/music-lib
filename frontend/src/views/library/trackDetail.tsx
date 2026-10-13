/* Детали трека: панель справа на широких экранах / модалка на узких;
   диалог текста (LRCLIB). */
import { coverUrl, del, get, post } from "../../lib/api";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import { asRenderableMessage, type RenderableMessage } from "../../i18n/messages";
import { toast } from "../../lib/toast";
import { fmtDuration, fmtSize } from "../../lib/format";
import { startJob } from "../../lib/jobs";
import type { OpHandle } from "../../lib/ops";
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { trackEditorDialog, runMetaflow } from "../../features/editor";
import { compressLabel, stemOf, type TrackRow } from "./libUtils";

export function TrackDetailBody({
  t,
  fromModal,
  onCloseModal,
  actions,
}: {
  t: TrackRow;
  fromModal?: boolean;
  onCloseModal?: () => void;
  actions: TrackDetailActions;
}) {
  const { t: translate } = useTranslation();
  const close = () => {
    if (fromModal) onCloseModal?.();
  };
  const coverBig = t.has_cover ? (
    <img
      src={coverUrl(t.path)}
      className="lib-bigcover"
    alt={translate("common.cover_alt", { title: `${t.artist ? `${t.artist} — ` : ""}${t.title || stemOf(t.path)}` })}
    />
  ) : (
    <div className="lib-nocover big" aria-hidden="true">♫</div>
  );
  const fields: [string, string][] = [
    [translate("editor.fields.title"), t.title || stemOf(t.path)],
    [translate("editor.fields.artist"), t.artist || "—"],
    [translate("editor.fields.album"), t.album || "—"],
    [translate("editor.fields.year"), t.year || "—"],
    [translate("editor.fields.genre"), t.genre || "—"],
    [translate("editor.fields.track_number"), t.track_number || "—"],
    [translate("editor.fields.disc_number"), t.disc_number || "—"],
    [translate("home.stats.duration"), fmtDuration(t.duration_seconds) || "—"],
    [translate("library.card.bitrate_title"), t.bitrate ? `${t.bitrate} kbps` : "—"],
    [translate("home.stats.size"), fmtSize(t.size_bytes)],
    [translate("library.track.compression_label"), compressLabel(t)],
  ];
  return (
    <div>
      {coverBig}
      <div>
        {fields.map(([k, v]) => (
          <div key={k}>
            <b>{`${k}: `}</b>
            {String(v)}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        <button style={{ width: "100%", minHeight: 44 }} type="button" onClick={() => { close(); void actions.editTags(t); }}>
          {translate("library.track.edit_tags")}
        </button>
        <div className="row lib-acts">
          <button className="small-btn ghost" type="button" onClick={() => { close(); void actions.metaflow(t); }}>
            {translate("library.track.meta_action")}
          </button>
          <button className="small-btn ghost" type="button" onClick={() => { close(); void actions.viewLyrics(t); }}>
            {translate("quality.lyrics.singular")}
          </button>
        </div>
        {t.need_compress ? (
          <button className="ghost" style={{ width: "100%" }} type="button" onClick={() => { close(); void actions.compress([t.path]); }}>
            {translate("library.compress.action")}
          </button>
        ) : null}
        <div style={{ borderTop: "1px solid var(--border)", marginTop: 6, paddingTop: 8 }}>
          <button
            className="small-btn danger ghost"
            style={{ width: "100%" }}
            type="button"
            onClick={() => { close(); void actions.deleteTrack(t); }}
          >
            {translate("library.track.delete_action")}
          </button>
        </div>
      </div>
    </div>
  );
}

export interface TrackDetailActions {
  editTags: (t: TrackRow) => Promise<void>;
  metaflow: (t: TrackRow) => Promise<void>;
  viewLyrics: (t: TrackRow) => Promise<void>;
  compress: (paths: string[]) => Promise<void>;
  deleteTrack: (t: TrackRow) => Promise<void>;
}

/* Модалка деталей трека (узкие экраны, карточки внутри альбома). */
export async function showTrackDetailModal(t: TrackRow, actions: TrackDetailActions): Promise<void> {
  await getDialogs().open({
    title: t.title || stemOf(t.path),
    build: ({ close }) => <TrackDetailBody t={t} fromModal actions={actions} onCloseModal={() => close(undefined)} />,
    actions: [{ title: i18n.t("library.track_detail.close"), class: "ghost", value: null, ok: true }],
  });
}

/* Диалог текста: pre.lyrics + «Обновить (LRCLIB)». */
export async function viewLyrics(path: string, after?: () => Promise<void>): Promise<void> {
  try {
    const data = await get<{ artist?: string; title?: string; lyrics?: string; synced_lyrics?: string }>("/api/lyrics", { path });
    const choice = await getDialogs().open({
      title: `${data.artist || ""} — ${data.title || ""}`,
      build: () => <pre className="lyrics">{data.synced_lyrics || data.lyrics || i18n.t("library.track_detail.no_lyrics")}</pre>,
      actions: [
        { title: i18n.t("library.track_detail.update_lyrics"), value: "update", ok: true },
        { title: i18n.t("library.track_detail.close"), class: "ghost", value: null, ok: true },
      ],
    });
    if (choice === "update") {
      const r = await post<{ updated: boolean }>("/api/lyrics/update", { path });
      if (r.updated) toast(i18n.t("library.track_detail.lyrics_updated"));
      else toast(i18n.t("library.track_detail.lyrics_not_found"), "warn");
      await after?.();
    }
  } catch (e) {
    toast(asRenderableMessage(e), "error");
  }
}

/* Редактор тегов + перезагрузка. */
export async function editTags(path: string, after: () => Promise<void>): Promise<void> {
  const updated = await trackEditorDialog(path, "", null, null, { autoFetch: true });
  if (updated) await after();
}

/* Метафлоу + перезагрузка. */
export async function metaflowTrack(path: string, after: () => Promise<void>): Promise<void> {
  if (await runMetaflow(path, "")) await after();
}

/* Удаление трека с подтверждением. */
export async function deleteTrack(
  t: TrackRow,
  after: () => Promise<void>,
  onDetailCleared?: (path: string) => void,
): Promise<void> {
  const ok = await getDialogs().confirm(i18n.t("library.track_detail.delete_confirm"), { defaultOk: false, okTitle: i18n.t("settings.delete") });
  if (!ok) return;
  try {
    await del("/api/library/track", { path: t.path });
    toast(i18n.t("library.track_detail.deleted"));
    onDetailCleared?.(t.path);
    await after();
  } catch (e) {
    toast(asRenderableMessage(e), "error");
  }
}

/* Пакетное сжатие выбранных треков (job + локальная прогресс-панель). */
export async function compressPaths(
  paths: string[],
  load: () => Promise<void>,
  startOp: () => OpHandle,
): Promise<void> {
  const op = startOp();
  try {
    const res = await startJob<{ label: RenderableMessage; done: number; skipped: number }>(
      "/api/compress",
      { mode: "audio", paths },
       { onProgress: (d) => op.set(d.percent ?? 0, d.message ?? d.msg) },
    );
    op.set(100, { code: "library.track_detail.compress_result", params: { label: res.label as unknown as import("../../i18n/messages").JsonValue, done: res.done, skipped: res.skipped } });
    await load();
  } catch (e) {
    op.set(0, "");
    toast(asRenderableMessage(e), "error");
  }
}
