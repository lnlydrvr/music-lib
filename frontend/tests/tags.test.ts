import { describe, expect, it } from "vitest";
import {
  normTagKey,
  pickAlbumRecord,
  providerFieldValue,
  validateTagField,
  type ProviderRecord,
} from "../src/lib/tags";

describe("validateTagField", () => {
  it("пустое значение допустимо", () => {
    expect(validateTagField("year", "")).toBe("");
    expect(validateTagField("track_number", null)).toBe("");
    expect(validateTagField("title", undefined)).toBe("");
  });

  it("год — ровно 4 цифры", () => {
    expect(validateTagField("year", "2024")).toBe("");
    expect(validateTagField("year", " 2024 ")).toBe("");
    expect(validateTagField("year", "24")).toBe("api.fields.year_four_digits");
    expect(validateTagField("year", "abcd")).toBe("api.fields.year_four_digits");
  });

  it("трек/диск — целое число", () => {
    expect(validateTagField("track_number", "7")).toBe("");
    expect(validateTagField("disc_number", "2")).toBe("");
    expect(validateTagField("track_number", "7a")).toBe("api.fields.integer_required");
    expect(validateTagField("disc_number", "-1")).toBe("api.fields.integer_required");
  });

  it("остальные поля без формата", () => {
    expect(validateTagField("title", "Что угодно!")).toBe("");
    expect(validateTagField("isrc", "USUM71703987")).toBe("");
  });
});

describe("providerFieldValue", () => {
  it("значение поля записи", () => {
    const rec = { source: "itunes", publisher: "UMG" } as ProviderRecord;
    expect(providerFieldValue(rec, "publisher")).toBe("UMG");
  });

  it("publisher фолбэк на label", () => {
    const rec = { source: "deezer", label: "Universal" } as ProviderRecord;
    expect(providerFieldValue(rec, "publisher")).toBe("Universal");
  });

  it("нет записи — пустая строка", () => {
    expect(providerFieldValue(null, "title")).toBe("");
  });
});

describe("normTagKey", () => {
  it("регистр и пунктуация не важны", () => {
    expect(normTagKey("  The Best Of! ")).toBe("the best of");
    expect(normTagKey("The-Best.of")).toBe(normTagKey("the best of"));
  });
});

describe("pickAlbumRecord", () => {
  const chosen = { source: "itunes", album: "Abbey Road" } as ProviderRecord;

  it("совпадение альбома приоритетнее первой записи", () => {
    const records = [
      { source: "itunes", album: "Let It Be" },
      { source: "itunes", album: "Abbey Road" },
    ] as ProviderRecord[];
    expect(pickAlbumRecord(records, chosen)?.album).toBe("Abbey Road");
  });

  it("нет совпадения альбома — первая запись источника", () => {
    const records = [{ source: "itunes", album: "Let It Be" }] as ProviderRecord[];
    expect(pickAlbumRecord(records, chosen)?.album).toBe("Let It Be");
  });

  it("источника нет — null", () => {
    const records = [{ source: "deezer", album: "Abbey Road" }] as ProviderRecord[];
    expect(pickAlbumRecord(records, chosen)).toBeNull();
    expect(pickAlbumRecord([], chosen)).toBeNull();
    expect(pickAlbumRecord(null, chosen)).toBeNull();
  });
});
