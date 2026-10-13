import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync("src/styles.css", "utf8");

describe("компактные действия дока загрузок", () => {
  it("держит «Очистить» компактной текстовой ghost-кнопкой", () => {
    expect(styles).toMatch(/\.dl-clear \{[^}]*flex-shrink: 0;[^}]*align-self: center;[^}]*min-height: 28px;[^}]*padding: 1px 7px;[^}]*font-size: 11px;/);
  });

  it("делает dismiss иконкой 28px, но 32px на coarse-указателе", () => {
    expect(styles).toMatch(/\.dl-item-dismiss \{[^}]*width: 28px;[^}]*height: 28px;[^}]*min-width: 28px;[^}]*min-height: 28px;/);
    expect(styles).toMatch(/@media \(pointer: coarse\)\s*\{[\s\S]*?\.dl-item-dismiss \{[^}]*width: 32px;[^}]*height: 32px;[^}]*min-width: 32px;[^}]*min-height: 32px;/);
  });
});
