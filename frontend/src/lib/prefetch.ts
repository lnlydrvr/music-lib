import type { ComponentType } from "react";
import type { RouteName } from "../routes";

/* Единственное место с импортерами ленивых экранов: отсюда их берёт React.lazy
   в App.tsx и отсюда же — префетч навигации. Карта чанков не расходится между
   lazy и прогревом: новый экран добавляется сюда одним ключом. */
export type ViewImporter = () => Promise<{ default: ComponentType }>;

export const ROUTE_IMPORTS: Record<RouteName, ViewImporter> = {
  menu: () => import("../views/MenuScreen"),
  library: () => import("../views/LibraryScreen"),
  discover: () => import("../views/DiscoverScreen"),
  recommend: () => import("../views/RecommendScreen"),
  quality: () => import("../views/QualityScreen"),
  settings: () => import("../views/SettingsScreen"),
};

/* Маршруты, уже запрошенные в этой сессии. Модульный кэш сам дедуплицирует
   import(), guard нужен, чтобы не плодить промисы на каждый hover. */
const requested = new Set<RouteName>();

/* Тихий префетч чанка экрана: идемпотентен и не бросает исключений — ошибки
   догрузки покажет React.lazy при реальном переходе. Неудачный запрос из guard
   снимается: следующий hover/focus попробует снова. */
export function prefetchRoute(route: RouteName): void {
  if (requested.has(route)) return;
  requested.add(route);
  ROUTE_IMPORTS[route]().catch(() => {
    requested.delete(route);
  });
}

/* Хендлеры для ссылок навигации: прогрев чанка по hover (pointerenter ловит и
   касание) и по фокусу с клавиатуры. Пассивно — без preventDefault. */
export function prefetchHandlers(route: RouteName): { onPointerEnter: () => void; onFocus: () => void } {
  return {
    onPointerEnter: () => prefetchRoute(route),
    onFocus: () => prefetchRoute(route),
  };
}
