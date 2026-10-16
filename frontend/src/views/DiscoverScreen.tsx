/* Общий экран «Загрузка»: Поиск и Shazam — табы. Контент каждого таба
   монтируется лениво при первом открытии и сохраняется между
   переключениями (не перерисовывается). Текущий таб — #/discover/{tab}. */
import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import SearchScreen from "./SearchScreen";
import MiscScreen from "./MiscScreen";
import LucidaScreen from "./LucidaScreen";

const TABS = ["search", "shazam", "lucida"] as const;

type TabId = (typeof TABS)[number];

function parseTab(hash: string): TabId {
  const m = hash.match(/^#\/discover\/(\w+)/);
  if (m && TABS.includes(m[1] as TabId)) return m[1] as TabId;
  return "search";
}

export default function DiscoverScreen() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>(() => parseTab(location.hash));
  /* Смонтированные табы живут до размонтирования экрана — состояние сохраняется. */
  const [mounted, setMounted] = useState<TabId[]>(() => [parseTab(location.hash)]);

  useEffect(() => {
    const onChange = () => {
      const id = parseTab(location.hash);
      setTab(id);
      setMounted((m) => (m.includes(id) ? m : [...m, id]));
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const activate = useCallback((id: TabId) => {
    setTab(id);
    setMounted((m) => (m.includes(id) ? m : [...m, id]));
    history.replaceState(null, "", `#/discover/${id}`);
  }, []);

  return (
    <>
      <div className="tabs" role="tablist" aria-label={t("discover.tabs_aria")}>
        {TABS.map((id) => (
          <button
            key={id}
            className={clsx("tab", id === tab && "active")}
            type="button"
            role="tab"
            aria-selected={id === tab}
            onClick={() => activate(id)}
          >
            {t(`discover.${id}`)}
          </button>
        ))}
      </div>
      <div className="tab-panel">
        {mounted.map((id) => (
          <div key={id} className="tab-pane" style={{ display: id === tab ? "" : "none" }}>
            {id === "search" ? <SearchScreen /> : id === "shazam" ? <MiscScreen /> : <LucidaScreen />}
          </div>
        ))}
      </div>
    </>
  );
}
