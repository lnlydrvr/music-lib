/* Скелетон «Проблем библиотеки» на время сканирования: строки той же
   структуры, что карточки отчёта (.quality-track: чекбокс · название/
   мета · пилюли проблем · действия), содержимое — пульсирующие полосы
   .skeleton. Инертен: без ховера и курсора (правила .quality-skeleton).
   Число строк фикс: реальный список неизвестен до ответа, важно занять
   высоту пары экранов, чтобы появление отчёта не прыгало. */
export function QualitySkeleton({ n = 6 }: { n?: number }) {
  return (
    <div className="quality-skeleton quality-track-list" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="quality-track">
          <div className="quality-check">
            <div className="skeleton" />
          </div>
          <div className="quality-track-info">
            <div className="quality-track-title">
              <div className="skeleton" style={{ width: `${55 + (i % 3) * 15}%` }} />
            </div>
            <div className="quality-track-meta">
              <div className="skeleton" style={{ width: `${35 + (i % 2) * 12}%` }} />
            </div>
          </div>
          <div className="quality-issues">
            <div className="skeleton" style={{ width: 110 }} />
            <div className="skeleton" style={{ width: 76 }} />
          </div>
          <div className="quality-actions">
            <div className="skeleton" style={{ width: 84 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
