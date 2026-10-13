/* Детали локального альбома: шапка с кнопками, треки (minimal), секция
   недостающих треков YT-двойника; диалоги «Общие теги альбома» и
   «Обложка для альбома». */
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { get, post, coverUrl } from "../../lib/api";
import { toast } from "../../lib/toast";
import i18n from "../../i18n";
import { validateTagField, type TagValidationCode } from "../../lib/tags";
import { resolveMessage, type RenderableMessage } from "../../i18n/messages";
import { getDialogs } from "../../components/dialogs/DialogProvider";
import { trackBatchEditorDialog } from "../../features/editor";
import { MinimalTrackRows } from "../../features/ytm/rows";
import { ytmDownload } from "../../features/ytm/download";
import type { YTMAlbum, YTMTrack } from "../../features/ytm/types";
import { ProgressBar } from "../../components/ui/ProgressBar";
import {
  ALBUM_COMMON_TAG_FIELDS,
  albumCommonValue,
  stemOf,
  type AlbumGroup,
  type TrackRow,
} from "./libUtils";
import { LocalAlbumCard, MergedAlbumCard, TrackCard } from "./Cards";
import type { YtApi } from "./useYtData";

export interface AlbumDetailActions {
  load: () => Promise<void>;
  openYtAlbum: (id: string, name: string) => void;
}

const FIELD_LABEL_KEYS = {
  artist: "editor.fields.artist",
  album: "editor.fields.album",
  album_artist: "editor.fields.album_artist",
  year: "editor.fields.year",
  genre: "editor.fields.genre",
  isrc: "editor.fields.isrc",
  composer: "editor.fields.composer",
  publisher: "editor.fields.publisher",
  comment: "editor.fields.comment",
} as const;
type FieldLabelKey = keyof typeof FIELD_LABEL_KEYS;

function resolveFieldLabel(field: string, t: (key: string) => string): string {
  const key = FIELD_LABEL_KEYS[field as FieldLabelKey];
  if (key) return t(key);
  if (import.meta.env.DEV || import.meta.env.MODE === "test") console.error("Unknown tag field label", field);
  return field;
}

export function AlbumDetailLocal({
  g,
  selected,
  toggleSelect,
  onBack,
  onOpenTrack,
  yt,
  actions,
}: {
  g: AlbumGroup;
  selected: Set<string>;
  toggleSelect: (path: string) => void;
  onBack: () => void;
  onOpenTrack: (t: TrackRow) => void;
  yt: YtApi;
  actions: AlbumDetailActions;
}) {
  const { t } = useTranslation();
  /* Секция недостающих треков YT-двойника — догружается после карточек. */
  const [missing, setMissing] = useState<{ tracks: YTMTrack[]; title: string; ytmId: string } | null>(null);
  const [nfo, setNfo] = useState<{ review: string; styles: string[] } | null>(null);
  const allSelected = g.tracks.length > 0 && g.tracks.every((t) => selected.has(t.path));

  useEffect(() => {
    let alive = true;
    setNfo(null);
    get<Partial<{ review: string; styles: string[] }>>("/api/library/album-nfo", { path: g.tracks[0]?.path || "" })
      .then((data) => alive && setNfo({ review: data.review || "", styles: data.styles || [] }))
      .catch(() => alive && setNfo({ review: "", styles: [] }));
    return () => {
      alive = false;
    };
  }, [g]);

  useEffect(() => {
    let alive = true;
    setMissing(null);
    (async () => {
      const twin = await yt.findAlbumTwin(g);
      if (!twin || !alive) return;
      try {
        const a = await get<YTMAlbum & { tracks?: YTMTrack[] }>("/api/ytmusic/album", { browse_id: twin.id });
        const list = (a.tracks || []).filter((t) => !t.in_library);
        if (alive && list.length) setMissing({ tracks: list, title: a.title || g.title, ytmId: twin.id });
      } catch {
        /* без двойника секции нет */
      }
    })();
    return () => {
      alive = false;
    };
  }, [g, yt]);

  return (
    <>
      <section className="panel lib-album-head" aria-label={t("library.album_detail.region")}>
        <button className="small-btn ghost" type="button" onClick={onBack}>{t("library.album_detail.back")}</button>
        {g.coverPath ? (
          <img src={coverUrl(g.coverPath)} className="lib-bigcover" alt={t("library.album_detail.cover_alt", { title: g.title })} />
        ) : (
          <div className="lib-nocover big" aria-hidden="true">♫</div>
        )}
        <div className="lib-album-meta">
          <div className="lib-album-title">{g.title}</div>
          <div className="muted">{g.artist || "—"}</div>
          <div className="row lib-album-actions">
            <button
              className="small-btn"
              type="button"
              title={t("library.album_detail.fill_tags_title")}
              onClick={() => void applyAlbumTags(g, actions.load)}
            >
              {t("library.album_detail.fill_tags")}
            </button>
            <button
              className="small-btn ghost"
              type="button"
              title={t("library.album_detail.common_tags_title")}
              onClick={() => void editAlbumCommonTags(g, actions.load)}
            >
              {t("library.album_detail.common_tags")}
            </button>
            <button
              className="small-btn ghost"
              type="button"
              title={t("library.album_detail.cover_title")}
              onClick={() => void pickAlbumCover(g, actions.load)}
            >
              {t("library.album_detail.cover")}
            </button>
          </div>
          {nfo?.review || nfo?.styles.length ? (
            <div className="album-nfo">
              {nfo.review ? <p className="album-nfo-review">{nfo.review}</p> : null}
              {nfo.styles.length ? (
                <div className="album-nfo-styles" aria-label={t("library.album_detail.genres")}>
                  {nfo.styles.map((style, index) => <span className="album-nfo-style" key={`${style}-${index}`}>{style}</span>)}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>
      {missing ? (
        <div className="panel">
          <div className="lib-missing-head">
            <b className="muted">{t("library.album_detail.missing", { count: missing.tracks.length })}</b>
            <button
              className="small-btn ghost"
              type="button"
              title={t("library.album_detail.download_all_title")}
              onClick={() =>
                void ytmDownload(missing.tracks, {
                  kind: "album",
                  providerId: missing.ytmId,
                  title: { code: "ytm.download.album_name", params: { title: missing.title } },
                }, () => actions.load())
              }
            >
              {t("library.album_detail.download_all", { count: missing.tracks.length })}
            </button>
          </div>
          <MinimalTrackRows
            tracks={missing.tracks}
            onDownload={(track) => void ytmDownload([track], {
              kind: "album",
              providerId: missing.ytmId,
              title: { code: "ytm.download.album_name", params: { title: missing.title } },
            }, () => actions.load())}
          />
        </div>
      ) : null}
      <section className="album-tracks" aria-label={t("library.album_detail.tracks_region")}>
        <div className="album-tracks-head">
          <b>{t("library.album_detail.tracks", { count: g.tracks.length })}</b>
          <button
            className={`small-btn ghost${allSelected ? " active" : ""}`}
            type="button"
            aria-pressed={allSelected}
            onClick={() => g.tracks.forEach((t) => toggleSelect(t.path))}
          >
            {allSelected ? t("library.album_detail.deselect_all") : t("library.album_detail.select_all", { count: g.tracks.length })}
          </button>
        </div>
        <div className="lib-grid" data-density="minimal">
          {g.tracks.map((t) => (
            <TrackCard
              key={t.path}
              t={t}
              showNum
              selected={selected.has(t.path)}
              onToggleSelect={toggleSelect}
              onOpen={onOpenTrack}
            />
          ))}
        </div>
      </section>
    </>
  );
}

/* «Выбрать теги для альбома»: batch-редактор по трекам альбома. */
export async function applyAlbumTags(g: AlbumGroup, load: () => Promise<void>): Promise<void> {
  const entries = g.tracks.map((t) => ({
    path: t.path,
    title: t.title || stemOf(t.path),
    artist: t.artist || "",
  }));
  const saved = await trackBatchEditorDialog(entries);
  const n = saved ? Object.keys(saved).length : 0;
  if (n) {
    toast(i18n.t("library.album_detail.saved", { count: n }));
    await load();
  }
}

/* «Общие теги альбома»: массовое применение заполненных полей одним диалогом. */
export async function editAlbumCommonTags(g: AlbumGroup, load: () => Promise<void>): Promise<void> {
  const apiBox: { current: (() => Promise<boolean>) | null } = { current: null };
  await getDialogs().open({
    title: i18n.t("library.album_detail.common_tags"),
    build: () => (
      <CommonTagsBody g={g} apiBox={apiBox} load={load} />
    ),
    actions: [
      { title: i18n.t("library.album_detail.apply"), onClick: () => apiBox.current?.() ?? false },
      { title: i18n.t("library.album_detail.cancel"), class: "ghost", value: null, ok: true },
    ],
  });
}

function CommonTagsBody({
  g,
  apiBox,
  load,
}: {
  g: AlbumGroup;
  apiBox: { current: (() => Promise<boolean>) | null };
  load: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [progress, setProgress] = useState<{ pct: number; msg: RenderableMessage } | null>(null);
  const values = useState(() => {
    const v: Record<string, string> = {};
    ALBUM_COMMON_TAG_FIELDS.forEach((f) => {
      v[f] = "";
    });
    return v;
  })[0];
  const [, force] = useState(0);

  apiBox.current = async () => {
    // Пустое поле — не изменение: отправляем только заполненные.
    const fields: Record<string, string> = {};
    const errs: { field: string; label: string; msg: TagValidationCode }[] = [];
    ALBUM_COMMON_TAG_FIELDS.forEach((field) => {
      const label = resolveFieldLabel(field, t);
      const v = values[field].trim();
      if (!v) return;
      const msg = validateTagField(field, v);
      if (msg) {
        errs.push({ field, label, msg });
        return;
      }
      fields[field] = v;
    });
    const bad = errs[0];
    if (bad) {
       toast({ code: "library.album_detail.invalid_field", params: { field: bad.label, message: t(bad.msg) } }, "error");
      document.querySelector<HTMLInputElement>(`[data-field="${bad.field}"] input`)?.focus();
      return false;
    }
    if (!Object.keys(fields).length) {
      toast(t("library.album_detail.fill_one"), "warn");
      return false;
    }
    let ok = 0;
    let fail = 0;
    for (let i = 0; i < g.tracks.length; i++) {
      setProgress({ pct: (i / g.tracks.length) * 100, msg: { code: "library.album_detail.applying", params: { index: i + 1, total: g.tracks.length } } });
      try {
        await post("/api/tags/apply", { path: g.tracks[i].path, fields, apply_cover: false });
        ok += 1;
      } catch {
        fail += 1;
      }
    }
    toast(
      t("library.album_detail.applied", { ok, fail }),
      fail ? "warn" : "",
    );
    await load();
    return true;
  };

  if (progress != null) return <ProgressBar pct={progress.pct} msg={resolveMessage(progress.msg)} />;

  return (
    <>
      <div className="muted" style={{ marginBottom: 8 }}>
        {t("library.album_detail.common_intro", { title: g.title, count: g.tracks.length })}
      </div>
      <div>
        {ALBUM_COMMON_TAG_FIELDS.map((field) => {
          const label = resolveFieldLabel(field, t);
          const common = albumCommonValue(g.tracks, field);
          const ph = common == null ? t("library.album_detail.mixed_placeholder") : common ? t("library.album_detail.current_placeholder", { value: common }) : t("library.album_detail.unset_placeholder");
          return (
            <div key={field} className={`field-row${values[field].trim() ? " dirty" : ""}`} data-field={field}>
              <label className="field-label">{label}</label>
              <div className="field-input">
                <input
                  type="text"
                  placeholder={ph}
                  autoComplete="off"
                  value={values[field]}
                  onChange={(e) => {
                    values[field] = e.target.value;
                    force((n) => n + 1);
                  }}
                />
              </div>
              {common == null ? (
                <button
                  className="cand-chip"
                  type="button"
                  disabled
                  title={t("library.album_detail.mixed_title")}
                  aria-label={t("library.album_detail.mixed_aria", { field: label })}
                >
                  {t("library.album_detail.mixed")}
                </button>
              ) : common ? (
                <button
                  className="cand-chip"
                  type="button"
                  style={{ display: common === values[field].trim() ? "none" : undefined }}
                  title={t("library.album_detail.use_current_title")}
                  aria-label={t("library.album_detail.use_current_aria", { field: label })}
                  onClick={() => {
                    values[field] = common;
                    force((n) => n + 1);
                    document.querySelector<HTMLInputElement>(`[data-field="${field}"] input`)?.focus();
                  }}
                >
                  {common}
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
    </>
  );
}

interface CoverCandidate {
  source: string;
  cover_url: string;
  cover_from?: string;
}

interface UploadedCover {
  name: string;
  url: string;
  data: string;
  mime: string;
}

/* «Обложка для альбома»: кандидаты из файла трека и источников; применение
   ко всем трекам (теги не трогаются, картинка качается один раз). */
export async function pickAlbumCover(g: AlbumGroup, load: () => Promise<void>): Promise<void> {
  const apiBox: { current: (() => Promise<boolean>) | null } = { current: null };
  await getDialogs().open({
    title: i18n.t("library.album_detail.cover"),
    build: () => <CoverPickBody g={g} apiBox={apiBox} load={load} />,
    actions: [
      { title: i18n.t("library.album_detail.apply"), onClick: () => apiBox.current?.() ?? false },
      { title: i18n.t("library.album_detail.cancel"), class: "ghost", value: null, ok: true },
    ],
  });
}

function CoverPickBody({
  g,
  apiBox,
  load,
}: {
  g: AlbumGroup;
  apiBox: { current: (() => Promise<boolean>) | null };
  load: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [candidates, setCandidates] = useState<CoverCandidate[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [chosen, setChosen] = useState<CoverCandidate | null>(null);
  const [uploaded, setUploaded] = useState<UploadedCover | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<{ pct: number; msg: RenderableMessage } | null>(null);

  /* Кандидаты: обложка трека альбома + метаданные источников, до первой
     дорожки с обложками. */
  useEffect(() => {
    let alive = true;
    (async () => {
      const cands: CoverCandidate[] = [];
      const seen = new Set<string>();
      if (g.coverPath) {
        cands.push({ source: t("library.album_detail.cover"), cover_url: coverUrl(g.coverPath), cover_from: g.coverPath });
        seen.add(coverUrl(g.coverPath));
      }
      let fromSources = 0;
      for (const t of g.tracks) {
        let recs: { source?: string; cover_url?: string }[] = [];
        try {
          recs = (await post<{ records?: { source?: string; cover_url?: string }[] }>("/api/fetch/meta", { path: t.path })).records || [];
        } catch {
          recs = [];
        }
        for (const r of recs) {
          if (!r.cover_url || seen.has(r.cover_url)) continue;
          seen.add(r.cover_url);
          cands.push({ source: r.source || "", cover_url: r.cover_url });
          fromSources += 1;
        }
        if (fromSources) break;
      }
      if (alive) setCandidates(cands);
    })().catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [g]);

  apiBox.current = async () => {
    if (!chosen && !uploaded) {
      toast(t("library.album_detail.choose_cover_first"), "warn");
      return false;
    }
    let ok = 0;
    let fail = 0;
    for (let i = 0; i < g.tracks.length; i++) {
      setProgress({ pct: (i / g.tracks.length) * 100, msg: { code: "library.album_detail.applying", params: { index: i + 1, total: g.tracks.length } } });
      try {
        await post("/api/tags/apply", {
          path: g.tracks[i].path,
          fields: {},
          cover_url: uploaded || chosen?.cover_from ? "" : chosen?.cover_url || "",
          cover_from: uploaded ? "" : chosen?.cover_from || "",
          cover_data: uploaded?.data || "",
          cover_mime: uploaded?.mime || "",
          apply_cover: true,
        });
        ok += 1;
      } catch {
        fail += 1;
      }
    }
    toast(t("library.album_detail.cover_applied", { ok, fail }), fail ? "warn" : "");
    await load();
    return true;
  };

  if (progress != null) return <ProgressBar pct={progress.pct} msg={resolveMessage(progress.msg)} />;

  async function selectFile(file: File | undefined) {
    if (!file) return;
    if (!new Set(["image/jpeg", "image/png"]).has(file.type)) {
      toast(t("library.album_detail.invalid_cover_file"), "warn");
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    const data = dataUrl.split(",", 2)[1];
    if (!data) {
      toast(t("library.album_detail.cover_read_failed"), "error");
      return;
    }
    setUploaded({ name: file.name, url: dataUrl, data, mime: file.type });
    setChosen(null);
  }

  return (
    <>
      <div className="muted" style={{ marginBottom: 8 }}>{t("library.album_detail.cover_intro", { title: g.title })}</div>
      {failed ? <div className="muted">{t("library.album_detail.sources_unavailable")}</div> : null}
      {candidates == null && !failed ? <div className="empty">{t("library.album_detail.finding_covers")}</div> : null}
      {candidates != null ? (
        <div className="cover-pick-grid">
          {candidates.map((c) => (
            <div
              key={c.cover_url}
              className={`cover-pick-card${chosen === c && !uploaded ? " active" : ""}`}
              tabIndex={0}
              role="button"
              aria-pressed={chosen === c && !uploaded}
              aria-label={t("library.album_detail.choose_cover_aria", { source: c.source })}
              onClick={() => {
                setChosen(c);
                setUploaded(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setChosen(c);
                  setUploaded(null);
                }
              }}
            >
              <img src={c.cover_url} loading="lazy" alt={t("library.album_detail.cover_from_alt", { source: c.source })} />
              <div className="cover-pick-src">{c.source}</div>
            </div>
          ))}
          <label
            className={`cover-pick-card cover-upload${uploaded ? " active" : ""}${dragging ? " drag" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              void selectFile(e.dataTransfer.files?.[0]);
            }}
          >
            <input
              type="file"
              accept="image/jpeg,image/png"
              aria-label={t("library.album_detail.upload_file_aria")}
              hidden
              onChange={(e) => void selectFile(e.target.files?.[0])}
            />
            {uploaded ? (
              <>
                <img src={uploaded.url} alt={t("library.album_detail.uploaded_cover_alt", { name: uploaded.name })} />
                <div className="cover-pick-src">{uploaded.name}</div>
              </>
            ) : (
              <>
                <div className="cover-upload-mark" aria-hidden="true">+</div>
                <b>{t("library.album_detail.upload_cover")}</b>
                <div className="cover-pick-src">{t("library.album_detail.upload_hint")}</div>
              </>
            )}
          </label>
        </div>
      ) : null}
    </>
  );
}

/* Локальные карточки исполнителя (обогащённые двойниками) для YT-детали. */
export function buildArtistLocalCards(
  groups: AlbumGroup[],
  twins: Map<string, YTMAlbum | null>,
  nameTranslit: string,
  onOpen: (g: AlbumGroup) => void,
): ReactNode[] {
  return groups.map((g) => {
    const ya = twins.get(g.key) ?? null;
    if (!ya) return <LocalAlbumCard key={g.key} g={g} onOpen={onOpen} />;
    const have = ya.in_library_tracks || 0;
    const total = ya.track_count || have;
    if (total && have >= total) return <LocalAlbumCard key={g.key} g={g} ya={ya} onOpen={onOpen} />;
    return (
      <MergedAlbumCard key={g.key} g={g} ya={ya} have={have} total={total} nameTranslit={nameTranslit} onOpen={onOpen} />
    );
  });
}
