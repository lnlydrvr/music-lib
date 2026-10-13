import type { RouteName } from "./routes";
import type { TranslationKey } from "./i18n/messages";

export interface NavItem {
  route: RouteName;
  labelKey: TranslationKey;
  key: string; // цифра для kbd-чипа (хоткеи — фаза 1)
}

/* Верхняя навигация (1–6). */
export const NAV_ITEMS: NavItem[] = [
  { route: "menu", labelKey: "nav.home", key: "1" },
  { route: "library", labelKey: "nav.library", key: "2" },
  { route: "discover", labelKey: "nav.search", key: "3" },
  { route: "recommend", labelKey: "nav.recommendations", key: "4" },
  { route: "quality", labelKey: "nav.issues", key: "5" },
  { route: "settings", labelKey: "nav.settings", key: "6" },
];

/* Пункты, живущие в мобильном меню «Ещё». */
export const MORE_ITEMS: NavItem[] = [
  { route: "quality", labelKey: "nav.issues", key: "5" },
  { route: "recommend", labelKey: "nav.recommendations", key: "4" },
  { route: "settings", labelKey: "nav.settings", key: "6" },
];
