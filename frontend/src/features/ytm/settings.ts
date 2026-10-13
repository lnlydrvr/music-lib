/* Настройки, влияющие на загрузку YT Music (формат/качество/источник/no_clips).
   Кэшируются на сессию — как YTM.settings() старого SPA. */
import { get } from "../../lib/api";

let cached: Record<string, unknown> | null = null;

export async function ytmSettings(): Promise<Record<string, unknown>> {
  if (cached) return cached;
  try {
    cached = await get<Record<string, unknown>>("/api/settings");
  } catch {
    cached = {};
  }
  return cached;
}

/* Значение настройки с дефолтом (YTM._fmt). */
export function fmtSetting<T>(s: Record<string, unknown>, key: string, fallback: T): T {
  const v = s && s[key];
  return (v === undefined || v === null || v === "" ? fallback : v) as T;
}

export function resetYtmSettings(): void {
  cached = null;
}
