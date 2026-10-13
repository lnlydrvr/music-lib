/* Скелетоны списков на время загрузки. meta — правая колонка-полоса,
   чтобы заглушка зеркалила TrackRow/PlaylistRow с метой (длительность,
   счётчик треков). */
export function SkeletonRows({ n = 3, meta = false }: { n?: number; meta?: boolean }) {
  return (
    <div>
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="trackrow" aria-hidden="true">
          <div className="skeleton" style={{ width: 48, height: 48, borderRadius: 8 }} />
          <div className="t-main">
            <div className="skeleton" style={{ width: "60%", marginBottom: 6 }} />
            <div className="skeleton" style={{ width: "40%" }} />
          </div>
          {meta ? (
            <div className="t-meta">
              <div className="skeleton" style={{ width: 72 }} />
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
