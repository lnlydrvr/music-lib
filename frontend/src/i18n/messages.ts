import i18n from "./index";
import type { TFunction } from "i18next";
import type en from "../locales/en.json";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface StructuredMessage {
  code: string;
  params?: Record<string, JsonValue | StructuredMessage>;
  message?: string;
}

export type RenderableMessage = string | StructuredMessage;
type Join<Key extends string, Child extends string> = `${Key}.${Child}`;
type LeafKeys<Value> = Value extends string
  ? never
  : { [Key in keyof Value & string]: Value[Key] extends string ? Key : Join<Key, LeafKeys<Value[Key]>> }[keyof Value & string];

export type TranslationKey = LeafKeys<typeof en>;
type KeyFamily<Prefix extends string> = Extract<TranslationKey, `${Prefix}${string}`>;
type TranslationOptions = Record<string, unknown>;

type ApiDescriptorKey = KeyFamily<"api.">;
type QualityLabelKey = KeyFamily<"quality.category."> | KeyFamily<"quality.cause.">;
type EditorGroupKey = KeyFamily<"editor.groups.">;
export type RecommendationKey = KeyFamily<"recommend.apply."> | "recommend.dislike_swipe" | "recommend.dislike_key";
type DownloadLabelKey = KeyFamily<"ytm.download.">;

function translateKnown<Key extends TranslationKey>(key: Key, options?: TranslationOptions, t: TFunction = i18n.t): string {
  return t(key, options as never) as string;
}

function resolveCatalogDescriptor(code: string, params: TranslationOptions, t: TFunction): string | null {
  return i18n.exists(code) ? translateKnown(code as TranslationKey, params, t) : null;
}

/** Resolves an API-owned descriptor after runtime validation of its code. */
export function resolveApiDescriptor(value: StructuredMessage, t: TFunction = i18n.t): string | null {
  if (!value.code.startsWith("api.") || !i18n.exists(value.code)) return null;
  return translateKnown(value.code as ApiDescriptorKey, value.params, t);
}

export function resolveQualityLabel(key: string, t: TFunction = i18n.t): string {
  const category = `quality.category.${key}` as QualityLabelKey;
  if (i18n.exists(category)) return translateKnown(category, undefined, t);
  const cause = `quality.cause.${key}` as QualityLabelKey;
  return i18n.exists(cause) ? translateKnown(cause, undefined, t) : key;
}

export function resolveRecommendationKey(key: RecommendationKey, options?: TranslationOptions, t: TFunction = i18n.t): string {
  return translateKnown(key, options, t);
}

export function resolveDownloadLabel(key: DownloadLabelKey, options?: TranslationOptions, t: TFunction = i18n.t): string {
  return translateKnown(key, options, t);
}

export const FIELD_LABEL_KEYS = ["artist", "title", "album", "album_artist", "genre", "year", "cover", "track_number", "disc_number", "isrc", "composer", "publisher", "comment"] as const;
type FieldLabelKey = (typeof FIELD_LABEL_KEYS)[number];

function fieldLabelKey(field: FieldLabelKey): `editor.fields.${FieldLabelKey}` {
  return `editor.fields.${field}`;
}

export function resolveFieldLabel(field: JsonValue | undefined, t: TFunction = i18n.t): string {
  if (typeof field === "string" && (FIELD_LABEL_KEYS as readonly string[]).includes(field)) return translateKnown(fieldLabelKey(field as FieldLabelKey), undefined, t);
  if (import.meta.env.DEV || import.meta.env.MODE === "test") console.error("Unknown diagnostic field", field);
  return String(field ?? "");
}

export function resolveEditorGroupLabel(group: string, t: TFunction = i18n.t): string {
  const key = `editor.groups.${group}` as EditorGroupKey;
  return i18n.exists(key) ? translateKnown(key, undefined, t) : group;
}

export function resolveEditorValidation(code: string, t: TFunction = i18n.t): string {
  const descriptor = resolveApiDescriptor({ code }, t);
  return descriptor ?? code;
}

export function asRenderableMessage(value: unknown): RenderableMessage {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "renderableMessage" in value) {
    const message = (value as { renderableMessage?: unknown }).renderableMessage;
    if (typeof message === "string" || (message && typeof message === "object" && typeof (message as { code?: unknown }).code === "string")) {
      return message as RenderableMessage;
    }
  }
  if (value && typeof value === "object" && typeof (value as { code?: unknown }).code === "string") {
    return value as StructuredMessage;
  }
  if (value instanceof Error) return value.message;
  if (value && typeof value === "object" && typeof (value as { message?: unknown }).message === "string") {
    return (value as { message: string }).message;
  }
  return "";
}

export function resolveMessage(value: RenderableMessage, t: TFunction = i18n.t): string {
  if (typeof value === "string") return value;

  if (value && typeof value.code === "string") {
    const params = Object.fromEntries(
      Object.entries(value.params || {}).map(([key, param]) => [
        key,
        param && typeof param === "object" && !Array.isArray(param) && typeof (param as { code?: unknown }).code === "string"
          ? resolveMessage(param as unknown as StructuredMessage, t)
          : param,
      ]),
    );
    const apiMessage = resolveApiDescriptor({ ...value, params }, t);
    if (apiMessage) return apiMessage;
    if (["diagnostics.health.missing_tag", "diagnostics.lint.whitespace", "diagnostics.quality.change", "diagnostics.quality.duplicate_field"].includes(value.code)) {
      params.fieldLabel = resolveFieldLabel(params.field as JsonValue, t);
    }
    const catalogMessage = resolveCatalogDescriptor(value.code, params, t);
    if (catalogMessage) return catalogMessage;
  }

  if (import.meta.env.DEV || import.meta.env.MODE === "test") {
    console.error("Missing localized message code", value?.code);
  }
  if (typeof value?.message === "string" && value.message.trim()) return value.message;
  return t("common.errors.unavailable");
}
