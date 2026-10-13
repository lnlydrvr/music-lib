/* Скелетон «Настроек» на время чтения /api/settings (включая скан
   профилей браузеров): та же структура — sticky-шапка и сетка .set-grid
   из двух колонок карточек, в панелях пульсирующие полосы .skeleton. */
export function SettingsSkeleton() {
  const bar = (w: string, h = 14, mb = 10) => (
    <div className="skeleton" style={{ width: w, height: h, marginBottom: mb }} />
  );
  const card = (rows: number) => (
    <div className="panel">
      {bar("38%", 16, 12)}
      {Array.from({ length: rows }, (_, i) => bar(`${52 + ((i * 13) % 38)}%`))}
    </div>
  );
  return (
    <div className="set-skeleton" aria-hidden="true">
      <div className="set-head">
        <div>
          {bar("130px", 24, 6)}
          {bar("280px", 12, 0)}
        </div>
      </div>
      <div className="set-grid">
        <div className="set-col">
          {card(4)}
          {card(5)}
        </div>
        <div className="set-col">
          {card(4)}
          {card(2)}
          {card(2)}
        </div>
      </div>
    </div>
  );
}
