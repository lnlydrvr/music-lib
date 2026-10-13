/* Shazam — импорт файла «Название - Исполнитель». */
import { useCallback, useEffect, useState } from "react";
import { post } from "../lib/api";
import { toast } from "../lib/toast";
import { startJob } from "../lib/jobs";
import { useOps, OpPanels } from "../lib/ops";
import { fmtDuration } from "../lib/format";
import { useDialogs } from "../components/dialogs/DialogProvider";
import { PreviewButton } from "../components/PreviewButton";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { Table } from "../components/ui/Table";
import { runMetaflow } from "../features/editor";
import { metaflowStageMessage } from "../features/editor";
import { useTranslation } from "react-i18next";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../i18n/messages";

interface ShazamHit {
  id: string;
  title: string;
  uploader: string;
  duration: number;
  url: string;
  cover_url: string;
  score: number;
}

interface ShazamEntry {
  index: number;
  line_number: number;
  title: string;
  artist: string;
  display: string;
  found: ShazamHit[];
}

interface ScanResult {
  file: string;
  entries: ShazamEntry[];
}

export default function MiscScreen() {
  const { t } = useTranslation();
  const dialogs = useDialogs();
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const [scanError, setScanError] = useState<RenderableMessage>("");
  const { ops, start: startOp } = useOps();

  const runScan = useCallback(async () => {
    setScanning(true);
    setNotConfigured(false);
    setScanError("");
    setScan(null);
    const op = startOp();
    try {
      const res = await startJob<ScanResult>("/api/shazam/scan", {}, { onProgress: (d) => op.set(d.percent ?? 0, d.message ?? d.msg) });
      setScan(res);
    } catch (e) {
      op.set(0, "");
      const message = asRenderableMessage(e);
      if (typeof message !== "string" && message.code === "jobs.shazam.file_missing") {
        // Файл Shazam не настроен: объясняем и даём путь к настройкам.
        setNotConfigured(true);
      } else {
        setScanError(message);
      }
    }
    setScanning(false);
  }, [startOp]);

  useEffect(() => {
    void runScan();
  }, [runScan]);

  /* Скачивание совпадения: /api/download → метафлоу → перенос → удаление
     строки из файла → повторное сканирование. */
  async function downloadMatch(entry: ShazamEntry, hit: ShazamHit) {
    const op = startOp([
      { id: "download", label: { code: "jobs.download.name" } },
      { id: "meta", label: { code: "shazam.stage.metadata" } },
      { id: "lyrics", label: { code: "shazam.stage.lyrics" } },
      { id: "move", label: { code: "shazam.stage.library" } },
    ]);
    op.go("download", "active");
    let filepath = "";
    let thumb = "";
    try {
      const res = await startJob<{ filepath: string; info?: { thumbnail?: string } }>(
        "/api/download",
        { url: hit.url, move: false },
        { onProgress: (d) => { if (d.percent != null) op.set(d.percent, d.message ?? d.msg); }, title: hit.title || hit.url },
      );
      filepath = res.filepath;
      thumb = res.info?.thumbnail || hit.cover_url || "";
      op.set(100, { code: "search.metaflow.downloaded_processing" });
      op.go("download", "done");
      op.go("meta", "active");
      op.set(80, { code: "search.metaflow.metadata_searching" });
      const ok = await dialogs.confirm(t("search.metaflow.confirm"), { defaultOk: true, okTitle: t("dialogs.yes"), cancelTitle: t("search.metaflow.skip") });
      if (ok) {
        await runMetaflow(filepath, thumb, (step) => {
          op.set(85, metaflowStageMessage(step));
          if (step === "lyrics") {
            op.go("meta", "done");
            op.go("lyrics", "active");
          }
        });
      } else {
        op.go("meta", "done");
        op.go("lyrics", "active");
        op.set(90, { code: "search.metaflow.lyrics_updating" });
      }
      op.go("lyrics", "done");
      op.go("move", "active");
      op.set(95, { code: "search.metaflow.moving" });
      await post("/api/library/move", { path: filepath });
      op.go("move", "done");
      op.set(100, { code: "search.metaflow.moved", params: { path: entry.display } });
      try {
        await post("/api/shazam/remove", { line_number: entry.line_number });
      } catch {
        /* строка могла уже уйти */
      }
      toast(t("search.metaflow.added_to_library"));
      await runScan();
    } catch (e) {
      op.go("download", "error");
      op.set(0, "");
      toast(asRenderableMessage(e), "error");
    }
  }

  async function removeLine(entry: ShazamEntry) {
    const ok = await dialogs.confirm(t("shazam.remove.confirm"), { okTitle: t("settings.delete") });
    if (!ok) return;
    try {
      const res = await post<{ removed: number }>("/api/shazam/remove", { line_number: entry.line_number });
      toast(t("shazam.remove.done", { count: res.removed }));
      await runScan();
    } catch (e) {
      toast(asRenderableMessage(e), "error");
    }
  }

  return (
    <div>
      <h1>Shazam</h1>
      <div className="comment">{t("shazam.subtitle")}</div>
      <button type="button" onClick={() => void runScan()}>
        {t("shazam.search")}
      </button>
      <div style={{ marginTop: 14 }}>
        <OpPanels ops={ops} />
        {scanning ? <Spinner text={t("shazam.searching")} /> : null}
        {notConfigured ? (
          <EmptyState
            art="⚙"
            title={t("shazam.unconfigured")}
            sub={t("shazam.unconfigured_hint")}
            action={
              <button className="btn-big ghost" type="button" onClick={() => { location.hash = "#/settings"; }}>
                {t("shazam.open_settings")}
              </button>
            }
          />
        ) : null}
        {scanError ? (
          <div className="panel" style={{ borderColor: "var(--danger)" }}>{resolveMessage(scanError)}</div>
        ) : null}

        {scan ? (
          <>
            <div className="muted" style={{ marginBottom: 8 }}>{t("shazam.file", { path: scan.file })}</div>
            {scan.entries.length ? (
              <>
                <Table headers={["", "", t("editor.fields.title"), t("editor.fields.artist"), t("shazam.duration")] }>
                  {scan.entries.map((entry) => (
                    <Rows key={entry.line_number} entry={entry} onDownload={downloadMatch} onRemove={removeLine} />
                  ))}
                </Table>
                <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
                  {t("shazam.download_hint")}
                </div>
              </>
            ) : (
              <div className="empty">{t("ytm.empty")}</div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

/* Строки одного распознанного трека: заголовок-группа + совпадения. */
function Rows({
  entry,
  onDownload,
  onRemove,
}: {
  entry: ShazamEntry;
  onDownload: (e: ShazamEntry, f: ShazamHit) => void;
  onRemove: (e: ShazamEntry) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <tr className="group">
        <td colSpan={5}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <b>{entry.display}</b>
            <button
              className="small-btn ghost danger"
              type="button"
              title={t("shazam.remove.title")}
              aria-label={t("shazam.remove.aria", { entry: entry.display })}
              onClick={() => onRemove(entry)}
            >
              {t("shazam.remove.action")}
            </button>
          </div>
        </td>
      </tr>
      {entry.found.length ? (
        entry.found.map((f, i) => (
          <tr key={f.id || i}>
            <td>
              <button className="small-btn" type="button" onClick={() => onDownload(entry, f)}>
                {t("search.download")}
              </button>
            </td>
            <td>
              <PreviewButton url={f.url} title={f.title} artist={f.uploader} coverUrl={f.cover_url} />
            </td>
            <td>
              <b>{f.title}</b>
            </td>
            <td className="muted">{f.uploader}</td>
            <td className="muted">{t("shazam.match", { duration: fmtDuration(f.duration), score: Math.round(f.score * 100) })}</td>
          </tr>
        ))
      ) : (
        <tr>
          <td />
          <td />
          <td className="muted">{t("shazam.no_matches")}</td>
          <td />
          <td />
        </tr>
      )}
    </>
  );
}
