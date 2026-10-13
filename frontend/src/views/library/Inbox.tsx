/* Inbox — файлы вне папок: карточки с действиями + групповые операции. */

import { post, del, coverUrl } from "../../lib/api";
import { toast } from "../../lib/toast";
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { runMetaflow } from "../../features/editor";
import { CollapsibleGroup } from "../../components/ui/CollapsibleGroup";
import { useTranslation } from "react-i18next";
import { stemOf, type TrackRow } from "./libUtils";
import type { TrackDetailActions } from "./trackDetail";
import type { OpHandle } from "../../lib/ops";
import { asRenderableMessage } from "../../i18n/messages";

export function InboxSection({
  list,
  density,
  actions,
  load,
  startProgress,
}: {
  list: TrackRow[];
  density: string;
  actions: TrackDetailActions;
  load: () => Promise<void>;
  /* Локальная прогресс-панель циклов переноса/удаления (useOps корня). */
  startProgress: () => OpHandle;
}) {
  const { t: translate } = useTranslation();
  async function moveInbox(path: string) {
    try {
      const res = await post<{ to: string }>("/api/library/move", { path });
      toast(translate("library.inbox.moved_to", { path: res.to }));
      await load();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }

  async function moveAllInbox() {
    if (!list.length) return;
    const ok = await getDialogs().confirm(
      translate("library.inbox.move_confirm", { count: list.length }),
      { defaultOk: false, okTitle: translate("library.inbox.move_action") },
    );
    if (!ok) return;
    const p = startProgress();
    let moved = 0;
    let failed = 0;
    for (let i = 0; i < list.length; i++) {
      p.set(Math.round((i / list.length) * 100), translate("library.inbox.item_progress", { index: i + 1, total: list.length, title: list[i].title || stemOf(list[i].path) }));
      try {
        await post("/api/library/move", { path: list[i].path });
        moved += 1;
      } catch {
        failed += 1;
      }
    }
    p.set(100, translate(failed ? "library.inbox.move_summary_errors" : "library.inbox.move_summary", { count: moved, failed }));
    await load();
  }

  async function deleteAllInbox() {
    if (!list.length) return;
    const ok = await getDialogs().open({
      title: translate("library.inbox.delete_all_title"),
      build: () => (
        <>
          <div>{translate("library.inbox.delete_confirm", { count: list.length })}</div>
          <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            {translate("library.inbox.delete_warning")}
          </div>
          <div style={{ maxHeight: 280, overflow: "auto", border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-deep)", marginTop: 8 }}>
            {list.map((t) => (
              <div key={t.path} style={{ padding: "3px 10px", fontSize: 12 }}>
                {t.title || stemOf(t.path)}
              </div>
            ))}
          </div>
        </>
      ),
      actions: [
        { title: translate("dialogs.cancel"), class: "ghost", value: false, ok: true },
        { title: translate("library.inbox.delete_all"), class: "danger", value: true, ok: true },
      ],
    });
    if (!ok) return;
    const p = startProgress();
    let deletedCount = 0;
    let failed = 0;
    for (let i = 0; i < list.length; i++) {
      p.set(Math.round((i / list.length) * 100), translate("library.inbox.delete_item_progress", { index: i + 1, total: list.length }));
      try {
        await del("/api/library/track", { path: list[i].path });
        deletedCount += 1;
      } catch {
        failed += 1;
      }
    }
    p.set(100, translate(failed ? "library.inbox.delete_summary_errors" : "library.inbox.delete_summary", { count: deletedCount, failed }));
    await load();
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <button
          className="small-btn"
          type="button"
          onClick={() => void moveAllInbox()}
          aria-label={translate("library.inbox.move_all_aria", { count: list.length })}
        >
          {translate("library.inbox.move_all", { count: list.length })}
        </button>
        <button
          className="small-btn danger ghost"
          type="button"
          onClick={() => void deleteAllInbox()}
          aria-label={translate("library.inbox.delete_all_aria", { count: list.length })}
        >
          {translate("library.inbox.delete_all")}
        </button>
      </div>
      <CollapsibleGroup title={translate("library.inbox.heading", { count: list.length })} className="group-inbox">
        <div className="lib-grid" data-density={density}>
          {list.map((t) => (
            <div key={t.path} className="lib-card inbox">
              <div className="lib-cover">
                {t.has_cover ? (
                  <img
                    src={coverUrl(t.path)}
                    loading="lazy"
                    alt={translate("common.cover_alt", { title: `${t.artist ? `${t.artist} — ` : ""}${t.title || stemOf(t.path)}` })}
                  />
                ) : (
                  <div className="lib-nocover" aria-hidden="true">♫</div>
                )}
              </div>
              <div className="lib-title">{t.title || stemOf(t.path)}</div>
              <div className="lib-sub">{t.artist || ""}</div>
              <div className="row lib-acts">
                <button className="small-btn ghost" type="button" onClick={() => void actions.editTags(t)}>{translate("library.selection.tags")}</button>
                <button
                  className="small-btn ghost"
                  type="button"
                  onClick={() => {
                    void runMetaflow(t.path, "").then((ok) => {
                      if (ok) void load();
                    });
                  }}
                >
                  {translate("library.track.meta_action")}
                </button>
                <button className="small-btn ghost" type="button" onClick={() => void actions.viewLyrics(t)}>{translate("quality.lyrics.singular")}</button>
                <button className="small-btn" type="button" onClick={() => void moveInbox(t.path)}>{translate("recommend.apply.library")}</button>
                <button className="small-btn danger ghost" type="button" onClick={() => void actions.deleteTrack(t)}>{translate("settings.delete")}</button>
              </div>
            </div>
          ))}
        </div>
      </CollapsibleGroup>
    </div>
  );
}
