import { useEffect, useState } from "react";
import NumberFlow from "@number-flow/react";
import type { RouteName } from "../routes";
import type { Theme } from "../hooks/useTheme";
import { NAV_ITEMS } from "../nav";
import { api } from "../lib/api";
import { fmtSize } from "../lib/format";
import { prefetchHandlers } from "../lib/prefetch";
import { useTranslation } from "react-i18next";

interface TopbarProps {
  route: RouteName;
  theme: Theme;
  onToggleTheme: () => void;
}

// Статистика библиотеки в топбаре: «[NN%] N треков · размер».
// NN — процент здоровья (треки без проблем из /api/library/quality), обновление каждые 30 секунд.
// Числа — NumberFlow (плавная смена цифр при обновлении).
function LibStats() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<{ tracks: number; sizeMb: number } | null>(null);
  const [health, setHealth] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const s = await api.get<{ tracks: number; size_mb: number }>("/api/state");
        if (!alive) return;
        setStats({ tracks: s.tracks, sizeMb: s.size_mb });
      } catch {
        /* сервер недоступен — оставляем прошлые значения */
      }
      try {
        const q = await api.get<{ total: number; tracks: unknown[] }>("/api/library/quality");
        if (!alive) return;
        setHealth(q.total > 0 ? Math.round((100 * (q.total - q.tracks.length)) / q.total) : null);
      } catch {
        if (alive) setHealth(null); // отчёт не получен — без процента
      }
    };
    load();
    const t = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const healthColor = health == null ? undefined : health >= 95 ? "var(--ok)" : health >= 85 ? "var(--warn)" : "var(--danger)";

  return (
    <span id="sidebar-stats">
      {health != null && (
        <span className="stats-health" style={{ color: healthColor }} title={t("shell.stats.health_title")}>
          [<NumberFlow value={health} format={{ useGrouping: false }} />%]{" "}
        </span>
      )}
      {stats ? (
        <>
          {t("shell.stats.tracks", { count: stats.tracks, size: fmtSize(stats.sizeMb * 1024 * 1024) })}
        </>
      ) : null}
    </span>
  );
}

export function Topbar({ route, theme, onToggleTheme }: TopbarProps) {
  const { t } = useTranslation();
  return (
    <header id="topbar">
      <div className="topbar-inner">
        <a className="brand" href="#/menu" {...prefetchHandlers("menu")}>
          $ music-lib
        </a>
        <nav id="nav" aria-label={t("shell.nav.main_aria")}>
          {NAV_ITEMS.map((item) => (
            <a
              key={item.route}
              href={`#/${item.route}`}
              data-view={item.route}
              className={item.route === route ? "active" : undefined}
              aria-current={item.route === route ? "page" : undefined}
              {...prefetchHandlers(item.route)}
            >
              <span className="kbd">{item.key}</span>
              {t(item.labelKey)}
            </a>
          ))}
        </nav>
        <div className="topbar-right">
          <LibStats />
          <button
            id="theme-toggle"
            className="theme-row"
            title={t("shell.theme.switch")}
            aria-pressed={theme === "light"}
            aria-label={t("shell.theme.switch")}
            onClick={onToggleTheme}
          >
            <span className="kbd" aria-hidden="true">t</span>
            <span id="theme-label">{t(theme === "light" ? "shell.theme.light" : "shell.theme.dark")}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
