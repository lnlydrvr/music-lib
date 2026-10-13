/* Скелетон главной на время загрузки /api/home: повторяет секции
   HomeBody — панель статистики из 5 чипов, .home-cols с «Последними
   добавленными» (строки-треки: обложка 40 + название/альбом + формат/
   дата справа) и «Статистикой» (точка + имя + счётчик, как StatRow),
   ниже пара карточек «Здоровье»/«Shazam». Грид-геометрия та же, что у
   реальной главной: инлайн auto-fit minmax + .home-cols (адаптив на
   900px доезжает и до скелетона), содержимое — пульсирующие полосы
   .skeleton. Инертен: правила .menu-skeleton. recent = 5 — столько
   треков отдаёт /api/home, stats — высота списка в maxHeight 300. */

function Bar({
  w,
  h = 13,
  mb,
  mt,
  center,
}: {
  w?: number | string;
  h?: number;
  mb?: number;
  mt?: number;
  center?: boolean;
}) {
  return (
    <div
      className="skeleton"
      style={{ width: w, height: h, marginBottom: mb, marginTop: mt, marginInline: center ? "auto" : undefined }}
    />
  );
}

/* Строка «Последних добавленных»: зеркало RecentRow (Cover 40 +
   artist — title / альбом + tag формата и дата). */
function RecentRow({ i }: { i: number }) {
  return (
    <div
      className="sk-recent-row"
      style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 0", borderBottom: "1px solid var(--border)" }}
    >
      <div className="skeleton" style={{ width: 40, height: 40, borderRadius: 8, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Bar w={`${60 + (i % 3) * 10}%`} h={13} mb={3} />
        <Bar w={`${35 + (i % 2) * 10}%`} h={11} />
      </div>
      <div style={{ textAlign: "end", flexShrink: 0 }}>
        <Bar w={44} h={17} />
        <Bar w={58} h={10} mt={3} />
      </div>
    </div>
  );
}

/* Строка «Статистики»: зеркало StatRow (точка-акцент + имя + счётчик). */
function StatRow({ i }: { i: number }) {
  return (
    <div
      className="sk-stat-row"
      style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", borderBottom: "1px solid var(--border)" }}
    >
      <div className="skeleton sk-dot" style={{ flexShrink: 0 }} />
      <Bar w={`${45 + (i % 3) * 15}%`} h={13} />
      <Bar w={56} h={11} />
    </div>
  );
}

export function MenuSkeleton({ recent = 5, stats = 6 }: { recent?: number; stats?: number }) {
  return (
    <div className="menu-skeleton" aria-hidden="true">
      {/* Статистика библиотеки: 5 чипов в auto-fit-гриде (как реальная). */}
      <div className="panel" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12 }}>
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="panel sk-chip" style={{ margin: 0, textAlign: "center", minWidth: 0 }}>
            <Bar w={64} h={24} center />
            <Bar w={84} h={12} mt={4} center />
          </div>
        ))}
      </div>

      <div className="home-cols">
        {/* Последние добавленные. */}
        <div className="panel">
          <Bar w="42%" h={12} mb={8} />
          {Array.from({ length: recent }, (_, i) => (
            <RecentRow key={i} i={i} />
          ))}
        </div>

        {/* Статистика: шапка с парой small-btn + строки StatRow. */}
        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <Bar w="38%" h={12} />
            <div style={{ display: "flex", gap: 8 }}>
              <Bar w={62} h={24} />
              <Bar w={88} h={24} />
            </div>
          </div>
          {Array.from({ length: stats }, (_, i) => (
            <StatRow key={i} i={i} />
          ))}
        </div>
      </div>

      {/* Здоровье / Shazam: grid без отступа сверху — как в HomeBody. */}
      <div className="sk-cards" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
        {[0, 1].map((i) => (
          <div key={i} className="panel sk-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Bar w={96} h={12} />
              <Bar w={36} h={18} />
            </div>
            <Bar w="72%" h={11} mt={6} />
          </div>
        ))}
      </div>
    </div>
  );
}
