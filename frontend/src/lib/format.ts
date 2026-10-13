/* Locale-sensitive formatting of numeric library data. */
import i18n from "../i18n";

/** @deprecated Library callers should use complete ICU messages. */
export function plural(n: number, one: string, few: string, many: string): string {
  const category = new Intl.PluralRules(i18n.language).select(n);
  return category === "one" ? one : category === "few" ? few : many;
}

export function fmtSize(bytes?: number | null): string {
  if (!bytes) return "—";
  const mb = bytes / (1024 * 1024);
  const unit = mb >= 1024 ? "gigabyte" : "megabyte";
  const value = mb >= 1024 ? mb / 1024 : mb;
  return new Intl.NumberFormat(i18n.language, {
    style: "unit",
    unit,
    unitDisplay: "short",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
}

export function fmtDuration(sec?: number | null): string {
  if (!sec) return "";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

export function fmtDate(ts?: number | null): string {
  if (!ts) return "";
  return new Intl.DateTimeFormat(i18n.language, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(ts * 1000));
}
