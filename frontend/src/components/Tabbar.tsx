import type { RouteName } from "../routes";
import { NAV_ITEMS } from "../nav";
import { prefetchHandlers } from "../lib/prefetch";
import { useTranslation } from "react-i18next";

interface TabbarProps {
  route: RouteName;
  moreOpen: boolean;
  onToggleMore: () => void;
  onNavigate: () => void;
}

/* Мобильная навигация: первые три экрана + кнопка «Ещё». */
export function Tabbar({ route, moreOpen, onToggleMore, onNavigate }: TabbarProps) {
  const { t } = useTranslation();
  const tabs = NAV_ITEMS.slice(0, 3);
  const moreActive = ["quality", "recommend", "settings"].includes(route);

  return (
    <nav id="tabbar" aria-label={t("shell.nav.mobile_aria")}>
      {tabs.map((item) => (
        <a
          key={item.route}
          href={`#/${item.route}`}
          data-view={item.route}
          className={item.route === route ? "active" : undefined}
          aria-current={item.route === route ? "page" : undefined}
          onClick={onNavigate}
          {...prefetchHandlers(item.route)}
        >
          <span className="svg-ic" aria-hidden="true">
            {ICONS[item.route]}
          </span>
          <span className="lbl">{t(item.labelKey)}</span>
        </a>
      ))}
      <button
        id="tab-more"
        aria-expanded={moreOpen}
        aria-controls="more"
        aria-label={t("shell.more")}
        className={moreActive ? "active" : undefined}
        onClick={onToggleMore}
      >
        <span className="svg-ic" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="5" cy="12" r="1.6"></circle>
            <circle cx="12" cy="12" r="1.6"></circle>
            <circle cx="19" cy="12" r="1.6"></circle>
          </svg>
        </span>
        <span className="lbl">{t("shell.more")}</span>
      </button>
    </nav>
  );
}

/* Иконки таббара (тот же набор, что в старом SPA). */
const ICONS: Record<string, React.ReactNode> = {
  menu: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1Z"></path>
    </svg>
  ),
  library: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V6l12-2v12"></path>
      <circle cx="6" cy="18" r="3"></circle>
      <circle cx="18" cy="16" r="3"></circle>
    </svg>
  ),
  discover: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7"></circle>
      <line x1="21" y1="21" x2="16.5" y2="16.5"></line>
    </svg>
  ),
};
