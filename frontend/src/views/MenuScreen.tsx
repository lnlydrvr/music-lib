/* Главная — статистика, недавние треки, здоровье и навигация. */
import { useEffect, useState } from "react";
import clsx from "clsx";
import { get, coverUrl } from "../lib/api";
import { fmtDate, fmtDuration, fmtSize } from "../lib/format";
import { Cover } from "../components/ui/Cover";
import { EmptyState } from "../components/ui/EmptyState";
import { MenuSkeleton } from "./MenuSkeleton";
import { useTranslation } from "react-i18next";
import { asRenderableMessage, resolveMessage, type RenderableMessage } from "../i18n/messages";

const ASCII_HERO = [
  "                  _         ___ __",
  "  __ _  __ _____ (_)_______/ (_) /",
  " /  ' \\/ // (_-</ / __/___/ / / _ \\",
  "/_/_/_/\\_,_/___/_/\\__/   /_/_/_.__/",
].join("\n");

interface HomeData {
  state: {
    tracks: number;
    artists: number;
    albums: number;
    duration_seconds: number;
    size_mb: number;
  };
  genres: { name: string; count: number; pct: number }[];
  artists: { name: string; count: number; pct: number }[];
  recent: { artist: string; title: string; album: string; ext: string; mtime: number; path: string }[];
  health: { issues: number };
  shazam: { configured: boolean; count: number };
}

function StatRow({ name, count, pct, i }: { name: string; count: number; pct: number; i: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
      <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--accent)", opacity: 1 - i * 0.08, flexShrink: 0 }} />
      <b style={{ flex: 1 }}>{name}</b>
      <span className="muted">{`${count} · ${pct}%`}</span>
    </div>
  );
}

export default function MenuScreen() {
  const { t } = useTranslation();
  const [data, setData] = useState<HomeData | null>(null);
  const [error, setError] = useState<RenderableMessage>("");
  const [statMode, setStatMode] = useState<"genres" | "artists">("genres");

  useEffect(() => {
    let alive = true;
    get<HomeData>("/api/home")
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(asRenderableMessage(e)));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <>
      <h1 className="hero-ascii">
        <span className="visually-hidden">music-lib</span>
        <pre className="ascii-hero" aria-hidden="true">{ASCII_HERO}</pre>
      </h1>
      <div className="comment">{t("home.subtitle")}</div>
      <div className="hero">
        <button className="btn-big" type="button" onClick={() => { location.hash = "#/discover/search"; }}>
          {t("home.find_music")}
        </button>
        <button className="btn-big ghost" type="button" onClick={() => { location.hash = "#/quality"; }}>
          {t("home.tidy")}
        </button>
      </div>
      <div className="menu-home">
        {!data && !error ? <MenuSkeleton /> : null}
        {error ? (
          <div className="panel" style={{ borderColor: "var(--danger)" }}>{t("settings.browse.error", { reason: resolveMessage(error) })}</div>
        ) : null}
        {data ? <HomeBody data={data} statMode={statMode} setStatMode={setStatMode} /> : null}
      </div>
    </>
  );
}

function HomeBody({
  data,
  statMode,
  setStatMode,
}: {
  data: HomeData;
  statMode: "genres" | "artists";
  setStatMode: (m: "genres" | "artists") => void;
}) {
  const { t } = useTranslation();
  const st = data.state;
  const statChips: [string, string][] = [
    [t("library.tabs.tracks"), String(st.tracks)],
    [t("library.tabs.artists"), String(st.artists)],
    [t("library.tabs.albums"), String(st.albums)],
    [t("home.stats.duration"), fmtDuration(st.duration_seconds) || "—"],
    [t("home.stats.size"), fmtSize(st.size_mb * 1024 * 1024)],
  ];
  const issues = data.health.issues || 0;
  const statItems = statMode === "artists" ? data.artists : data.genres;

  return (
    <>
      <div className="panel" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12 }}>
        {statChips.map(([label, value]) => (
          <div key={label} className="panel" style={{ margin: 0, textAlign: "center", minWidth: 0 }}>
            <div style={{ fontSize: "clamp(20px,2.4vw,26px)", fontWeight: 700, color: "var(--accent)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {value}
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      <div className="home-cols">
        <div className="panel">
          <h2 style={{ margin: "0 0 8px" }}>{t("home.recent.title")}</h2>
          {data.recent.length ? (
            data.recent.map((t) => (
              <div
                key={t.path}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 0", borderBottom: "1px solid var(--border)", cursor: "pointer" }}
                onClick={() => { location.hash = "#/library?path=" + encodeURIComponent(t.path); }}
              >
                <Cover src={coverUrl(t.path)} size={40} alt={t.title} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b>{t.artist ? `${t.artist} — ${t.title}` : t.title}</b>
                  {t.album ? <div className="muted" style={{ fontSize: 12 }}>{t.album}</div> : null}
                </div>
                <div style={{ textAlign: "end", flexShrink: 0 }}>
                  <span className="tag">{t.ext.replace(".", "").toUpperCase()}</span>
                  <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>{fmtDate(t.mtime)}</div>
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              art="♫"
              title={t("home.recent.empty")}
              sub={t("home.recent.empty_hint")}
              action={
                <button className="small-btn ghost" type="button" onClick={() => { location.hash = "#/discover/search"; }}>
                  {t("home.find_music")}
                </button>
              }
            />
          )}
        </div>

        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>{t("home.stats.title")}</h2>
            <div className="row">
              <button className={clsx("small-btn ghost", statMode === "genres" && "active")} type="button" onClick={() => setStatMode("genres")}>
                {t("home.stats.genres")}
              </button>
              <button className={clsx("small-btn ghost", statMode === "artists" && "active")} type="button" onClick={() => setStatMode("artists")}>
                {t("library.tabs.artists")}
              </button>
            </div>
          </div>
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {statItems.length ? (
              statItems.map((it, i) => <StatRow key={it.name} name={it.name} count={it.count} pct={it.pct} i={i} />)
            ) : (
              <div className="muted">{t("ytm.empty")}</div>
            )}
          </div>
        </div>
      </div>

      {/* Как в menu.js: grid без отступа сверху — Panels сами дают
          вертикальный ритм через margin-bottom из styles.css. */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
        <a className="panel" href="#/quality" style={{ cursor: "pointer", color: "inherit", textDecoration: "none" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>{t("home.health.title")}</h2>
            <span className={`tag ${issues > 0 ? "bad" : "ok"}`}>{issues > 0 ? `✕ ${issues}` : "✓"}</span>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            {issues > 0 ? t("quality.screen.problems", { count: issues }) : t("home.health.ok")}
          </div>
        </a>
        <a className="panel" href="#/discover/shazam" style={{ cursor: "pointer", color: "inherit", textDecoration: "none" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>Shazam</h2>
            {data.shazam.count ? <span className="tag">{String(data.shazam.count)}</span> : null}
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            {data.shazam.configured ? (data.shazam.count ? t("home.shazam.queued", { count: data.shazam.count }) : t("ytm.empty")) : t("home.shazam.file_unconfigured")}
          </div>
        </a>
      </div>
    </>
  );
}
