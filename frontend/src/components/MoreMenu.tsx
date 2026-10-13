import { useEffect } from "react";
import type { RouteName } from "../routes";
import { MORE_ITEMS } from "../nav";
import { prefetchHandlers } from "../lib/prefetch";
import { useTranslation } from "react-i18next";

interface MoreMenuProps {
  route: RouteName;
  open: boolean;
  onClose: () => void;
}

/* Раскрывающееся меню «Ещё»: видимость управляется body-классом more-open
   (на нём же построен CSS старого SPA). */
export function MoreMenu({ route, open, onClose }: MoreMenuProps) {
  const { t } = useTranslation();
  useEffect(() => {
    document.body.classList.toggle("more-open", open);
    return () => document.body.classList.remove("more-open");
  }, [open]);

  return (
    <>
      <div id="more-backdrop" onClick={onClose}></div>
      <div id="more" role="menu" aria-label={t("shell.nav.more_aria")}>
        {MORE_ITEMS.map((item) => (
          <a
            key={item.route}
            href={`#/${item.route}`}
            data-view={item.route}
            role="menuitem"
            className={item.route === route ? "active" : undefined}
            aria-current={item.route === route ? "page" : undefined}
            onClick={onClose}
            {...prefetchHandlers(item.route)}
          >
            {t(item.labelKey)}
          </a>
        ))}
      </div>
    </>
  );
}
