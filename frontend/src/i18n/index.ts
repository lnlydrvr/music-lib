import i18n from "i18next";
import ICU from "i18next-icu";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import registry from "../locales/registry.json";

export const SUPPORTED_LOCALES = registry.map(({ code }) => code) as [string, ...string[]];
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export type LocaleInfo = { code: Locale; name: string };

const catalogs = import.meta.glob("../locales/*.json", { eager: true, import: "default", query: "?json" }) as Record<string, Record<string, unknown>>;

function pendingKeys(locale: string): string[] {
  const key = Object.keys(catalogs).find((path) => path.endsWith(`/${locale}.todo.json`));
  return key ? (catalogs[key] as unknown as string[]) : [];
}

export function removePending(value: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const result = structuredClone(value);
  for (const key of keys) {
    const parts = key.split(".");
    let current: Record<string, unknown> = result;
    for (const part of parts.slice(0, -1)) {
      const next = current[part];
      if (!next || typeof next !== "object" || Array.isArray(next)) {
        current = {};
        break;
      }
      current = next as Record<string, unknown>;
    }
    if (current !== result || parts.length === 1) delete current[parts.at(-1)!];
  }
  return result;
}

export const LOCALE_INFO: LocaleInfo[] = registry.map(({ code, name }) => ({ code: code as Locale, name }));
const resources = Object.fromEntries(
  LOCALE_INFO.map(({ code }) => {
    const path = Object.keys(catalogs).find((candidate) => candidate.endsWith(`/${code}.json`));
    const catalog = path ? catalogs[path] : {};
    return [code, { translation: code === "en" ? en : removePending(catalog, pendingKeys(code)) }];
  }),
);

const LANGUAGE_STORAGE_KEY = "music-lib-language";
const SETTINGS_BOOTSTRAP_TIMEOUT_MS = 5_000;

function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

function supportedLocale(value: unknown): Locale | null {
  if (typeof value !== "string") return null;
  const primary = value.toLowerCase().split("-")[0];
  return isLocale(primary) ? primary : null;
}

function setDocumentLanguage(locale: Locale) {
  document.documentElement.lang = locale;
}

export function resolveLanguage(serverLanguage: unknown, browserLanguage = navigator.language): Locale {
  return supportedLocale(serverLanguage) ?? supportedLocale(browserLanguage) ?? "en";
}

export function getProvisionalLanguage(browserLanguage = navigator.language): Locale {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return supportedLocale(stored) ?? resolveLanguage(null, browserLanguage);
  } catch {
    return resolveLanguage(null, browserLanguage);
  }
}

export const initialProvisionalLanguage = getProvisionalLanguage();

i18n
  .use(ICU)
  .use(initReactI18next)
  .init({
    resources,
    lng: initialProvisionalLanguage,
    fallbackLng: "en",
    interpolation: { escapeValue: false },
  });
setDocumentLanguage(initialProvisionalLanguage);

export async function changeLanguage(locale: Locale): Promise<void> {
  await i18n.changeLanguage(locale);
  setDocumentLanguage(locale);
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, locale);
  } catch {
    // Storage is an optional startup optimization, not the language authority.
  }
}

export async function bootstrapLanguage(browserLanguage = navigator.language): Promise<Locale> {
  let serverLanguage: unknown;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), SETTINGS_BOOTSTRAP_TIMEOUT_MS);
  try {
    const response = await fetch("/api/settings", { signal: controller.signal });
    if (!response.ok) return preserveProvisionalLanguage();
    serverLanguage = (await response.json() as { language?: unknown }).language;
  } catch {
    // Keep the provisional selection when the server cannot be reached.
    return preserveProvisionalLanguage();
  } finally {
    clearTimeout(timeout);
  }
  const locale = resolveLanguage(serverLanguage, browserLanguage);
  await changeLanguage(locale);
  return locale;
}

async function preserveProvisionalLanguage(): Promise<Locale> {
  const locale = supportedLocale(i18n.language) ?? initialProvisionalLanguage ?? "en";
  await changeLanguage(locale);
  return locale;
}

export { resolveMessage } from "./messages";
export default i18n;
