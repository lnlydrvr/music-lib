import { describe, expect, it } from "vitest";
import { wordDiff } from "../src/lib/diff";

function plain(parts: { t: string }[]) {
  return parts.map((p) => p.t).join("");
}

describe("wordDiff", () => {
  it("идентичные строки — без подсветки", () => {
    const { oldParts, newParts } = wordDiff("One Two Three", "One Two Three");
    expect(plain(oldParts)).toBe("One Two Three");
    expect(plain(newParts)).toBe("One Two Three");
    expect(oldParts.every((p) => !p.del && !p.add)).toBe(true);
  });

  it("вставка слова помечается add", () => {
    const { oldParts, newParts } = wordDiff("Beatles — Let It Be", "Beatles — Let It Be (Remastered)");
    expect(plain(oldParts)).toBe("Beatles — Let It Be");
    expect(plain(newParts)).toBe("Beatles — Let It Be (Remastered)");
    expect(newParts.some((p) => p.add && /\(Remastered\)/.test(p.t))).toBe(true);
    expect(oldParts.every((p) => !p.del)).toBe(true);
  });

  it("удаление слова помечается del", () => {
    const { oldParts, newParts } = wordDiff("Song (feat. Someone)", "Song");
    expect(plain(newParts)).toBe("Song");
    expect(oldParts.some((p) => p.del && p.t === "(feat." )).toBe(true);
    expect(newParts.every((p) => !p.add)).toBe(true);
  });

  it("замена слова — del в старой, add в новой", () => {
    const { oldParts, newParts } = wordDiff("Deep Purple", "Дип Пёрпл");
    const dels = oldParts.filter((p) => p.del).map((p) => p.t);
    const adds = newParts.filter((p) => p.add).map((p) => p.t);
    expect(dels).toContain("Deep");
    expect(adds).toContain("Дип");
  });

  it("пустые значения", () => {
    const a = wordDiff("", "Слово");
    expect(plain(a.oldParts)).toBe("");
    expect(a.newParts.every((p) => p.add)).toBe(true);
    const b = wordDiff("Слово", "");
    expect(plain(b.newParts)).toBe("");
    expect(b.oldParts.every((p) => p.del)).toBe(true);
    const c = wordDiff("", "");
    expect(c.oldParts).toEqual([]);
    expect(c.newParts).toEqual([]);
  });

  it("общие слова сохраняются на своих местах", () => {
    const { oldParts, newParts } = wordDiff("Alpha Beta", "Alpha Gamma");
    expect(oldParts[0].t).toBe("Alpha");
    expect(newParts[0].t).toBe("Alpha");
    expect(oldParts[0].del).toBeUndefined();
  });
});
