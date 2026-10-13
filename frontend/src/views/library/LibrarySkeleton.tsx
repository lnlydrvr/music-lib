/* Скелетон «Библиотеки»: на время загрузки повторяет раскладку активной
   вкладки — та же сетка .lib-grid[data-density] с .lib-card (обложка +
   title/sub) для альбомов/исполнителей/треков и строки .trackrow для
   плейлистов (как PlaylistRow). Классы совпадают с реальными карточками,
   поэтому число колонок и плотность определяет тот же CSS. */
import clsx from "clsx";

export type LibrarySkeletonView = "albums" | "artists" | "tracks" | "playlists";

/* Карточка сетки. album — колонка «обложка сверху + подпись» (альбомы/
   исполнители); иначе карточка трека: как TrackCard, с чекбоксом, строкой
   и колонками «Списка» (в full/compact их прячет тот же CSS, что и у
   настоящих карточек). Ширины полос чуть варьируются — не «частокол». */
function SkeletonCard({ album, i }: { album: boolean; i: number }) {
  return (
    <div className={clsx("lib-card", album && "album")}>
      {album ? null : (
        <label className="lib-check">
          <span className="sk-bar" />
        </label>
      )}
      <div className="lib-cover" />
      <div className="lib-mid">
        <div className="lib-title">
          <span className="sk-bar" style={{ width: `${70 + (i % 3) * 10}%` }} />
        </div>
        <div className="lib-sub">
          <span className="sk-bar" style={{ width: "55%" }} />
        </div>
      </div>
      {album ? null : (
        <>
          <div className="lib-rowline">
            <span className="sk-bar" style={{ width: `${55 + (i % 3) * 15}%` }} />
          </div>
          <div className="lib-cols">
            <span className="lc-year sk-bar" />
            <span className="lc-fmt sk-bar" />
            <span className="lc-dur sk-bar" />
            <span className="lc-size sk-bar" />
          </div>
        </>
      )}
    </div>
  );
}

/* Строка плейлиста: обложка 48 + title/sub + мета (как PlaylistRow). */
function SkeletonRow() {
  return (
    <div className="trackrow">
      <span className="cover cover-48" />
      <span className="t-main">
        <span className="t-title">
          <span className="sk-bar" style={{ width: "60%" }} />
        </span>
        <span className="t-sub">
          <span className="sk-bar" style={{ width: "40%" }} />
        </span>
      </span>
      <span className="t-meta">
        <span className="sk-bar" style={{ width: 72 }} />
      </span>
    </div>
  );
}

export function LibrarySkeleton({
  view,
  density = "full",
  n,
}: {
  view: LibrarySkeletonView;
  density?: string;
  n?: number;
}) {
  /* Сетка — пара рядов карточек, «Список» и плейлисты — строки. */
  const count = n ?? (view === "playlists" ? 4 : density === "minimal" ? 8 : 12);

  if (view === "playlists") {
    return (
      <div className="lib-skeleton" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    );
  }

  const albumCard = view === "albums" || view === "artists";
  return (
    <div className={clsx("lib-grid", "lib-skeleton")} data-density={density} aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <SkeletonCard key={i} album={albumCard} i={i} />
      ))}
    </div>
  );
}
