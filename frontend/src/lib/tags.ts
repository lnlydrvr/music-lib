/* Схема тегов редактора: группы, валидация, записи источников. */

export interface TagFieldGroup {
  group: string;
  fields: [field: string, label: string][];
}

export const TAG_FIELDS: TagFieldGroup[] = [
  { group: "Основное", fields: [
    ["title", "Название"], ["artist", "Исполнитель"],
    ["album", "Альбом"], ["album_artist", "Альбом-исполнитель"],
  ] },
  { group: "Релиз", fields: [
    ["year", "Год"], ["genre", "Жанр"],
    ["track_number", "Трек №"], ["disc_number", "Диск №"],
  ] },
  { group: "Прочее", fields: [
    ["isrc", "ISRC"], ["composer", "Композитор"],
    ["publisher", "Издатель / Лейбл"], ["comment", "Комментарий"],
  ] },
];

export const TAG_FIELD_LIST = TAG_FIELDS.flatMap((g) => g.fields);

export type TagValues = Record<string, string>;

export interface ProviderRecord {
  source: string;
  title?: string;
  artist?: string;
  album?: string;
  year?: string | number;
  cover_url?: string;
  label?: string;
  [key: string]: unknown;
}

export type TagValidationCode = "api.fields.year_four_digits" | "api.fields.integer_required";

/* Клиентская валидация — зеркало src/web/routes.py::_validate_tag_fields_map. */
export function validateTagField(field: string, value: unknown): TagValidationCode | "" {
  const v = String(value || "").trim();
  if (!v) return "";
  if (field === "year" && !/^\d{4}$/.test(v)) return "api.fields.year_four_digits";
  if ((field === "track_number" || field === "disc_number") && !/^\d+$/.test(v)) return "api.fields.integer_required";
  return "";
}

/* Значение поля из записи источника (у publisher фолбэк на label). */
export function providerFieldValue(rec: Partial<ProviderRecord> | null | undefined, field: string): string {
  let v = String((rec && (rec as Record<string, unknown>)[field]) || "");
  if (!v && field === "publisher") v = String((rec && rec.label) || "");
  return v;
}

/* Нормализованный ключ тега: регистр и пунктуация не важны. */
export function normTagKey(s: unknown): string {
  return String(s || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

/* Запись того же источника для «Выбрать теги для альбома»:
   приоритет — совпадение альбома с выбранной записью, иначе первая
   запись источника; null — у трека этот источник не нашёлся. */
export function pickAlbumRecord(records: ProviderRecord[] | null | undefined, chosen: ProviderRecord): ProviderRecord | null {
  const inSrc = (records || []).filter((r) => r.source === chosen.source);
  if (!inSrc.length) return null;
  const albumKey = normTagKey(chosen.album);
  if (albumKey) {
    const same = inSrc.filter((r) => normTagKey(r.album) === albumKey);
    if (same.length) return same[0];
  }
  return inSrc[0];
}
