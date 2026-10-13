/* Скачивание треков YouTube Music: job /api/ytmusic/download с настройками
   формата; progress живёт в общем доке загрузок (startJob). Имя архива строится
   только из kind и URL-кодированного providerId, никогда из display title. */
import { toast } from "../../lib/toast";
import { startJob } from "../../lib/jobs";
import { fmtSetting, ytmSettings } from "./settings";
import type { YtmDownloadResult, YTMTrack } from "./types";
import type { RenderableMessage } from "../../i18n/messages";
import { asRenderableMessage, resolveDownloadLabel, type TranslationKey } from "../../i18n/messages";
import i18n from "../../i18n";

export interface YtmDownloadTarget {
  kind: YtmDownloadKind;
  providerId: string;
  title: RenderableMessage;
}

export type YtmDownloadKind = "album" | "artist" | "playlist" | "radio" | "track" | "youtube";

function archiveNameFor(kind: YtmDownloadKind, id: string): string {
  return `ytm-${kind}-${encodeURIComponent(id)}`;
}

export async function ytmDownload(
  items: YTMTrack[],
  target: YtmDownloadTarget,
  onDone?: () => void | Promise<void>,
  onProgress?: (progress: { percent?: number | null; message?: RenderableMessage; msg?: RenderableMessage }) => void,
): Promise<YtmDownloadResult | null> {
  if (!items || !items.length) return null;
  const s = await ytmSettings();
  try {
    const res = await startJob<YtmDownloadResult>("/api/ytmusic/download", {
      items,
      // The API uses this as an archive filename. A descriptor belongs only to
      // the UI/job name, never to a filesystem-facing request field.
      playlist: archiveNameFor(target.kind, target.providerId),
      fmt: fmtSetting(s, "default_format", "m4a"),
      quality: fmtSetting(s, "default_quality", 160),
      source: fmtSetting(s, "source_format", ""),
      no_clips: fmtSetting<boolean>(s, "ytmusic_no_clips", true) !== false,
      move: true,
    }, { title: target.title, onProgress });
    toast(res.archive
      ? i18n.t("ytm.download.archive", { name: res.archive.split("/").pop() })
      : i18n.t("ytm.download.completed", { count: res.ok }));
    if (onDone) await onDone();
    return res;
  } catch (e) {
    toast(asRenderableMessage(e), "error");
    return null;
  }
}

/* Кнопка «Скачать отсутствующие (N)» / «Всё уже в библиотеке». */
export function downloadAllLabel(n: number, labelKey?: Extract<TranslationKey, `ytm.download.${string}`>): string {
  return n
    ? labelKey ? resolveDownloadLabel(labelKey, { count: n }) : i18n.t("ytm.download.all_missing", { count: n })
    : i18n.t("ytm.download.already_in_library");
}
