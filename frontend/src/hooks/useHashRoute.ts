import { useEffect, useState } from "react";
import { parseRoute, type RouteName } from "../routes";

/* Текущий маршрут из location.hash; deep-link параметры (?path=) не теряются —
   остаются в URL, парсится только имя экрана. */
export function useHashRoute(): RouteName {
  const [route, setRoute] = useState<RouteName>(() => parseRoute(location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseRoute(location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}
