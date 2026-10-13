/* Маршруты SPA: hash → имя экрана. */

export const ROUTES = [
  "menu",
  "library",
  "discover",
  "recommend",
  "quality",
  "settings",
] as const;

export type RouteName = (typeof ROUTES)[number];

/* `#/library?path=...` → "library"; query-часть остаётся в URL (deep-links фазы 3). */
export function parseRoute(hash: string): RouteName {
  const m = hash.match(/^#\/([\w-]+)/);
  const name = m?.[1] ?? "menu";
  return (ROUTES as readonly string[]).includes(name) ? (name as RouteName) : "menu";
}
