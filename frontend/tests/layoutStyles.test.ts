import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync("src/styles.css", "utf8");

function luminance(hex: string): number {
  const rgb = hex.slice(1).match(/.{2}/g)!.map((v) => parseInt(v, 16) / 255);
  const linear = rgb.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

function contrast(foreground: string, background: string): number {
  const [a, b] = [luminance(foreground), luminance(background)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}

describe("адаптивная раскладка", () => {
  it("использует Zed semantic palette for the interface", () => {
    expect(styles).toContain("--surface: #21252B;");
    expect(styles).toContain("--surface-2: #282C34;");
    expect(styles).toContain("--surface-3: #2E323C;");
    expect(styles).toContain("--accent: #61AFEF;");
    expect(styles).toContain("--accent-strong: #85C1FF;");
    expect(styles).toContain("--accent-soft: rgba(97, 175, 239, .16);");
    expect(styles).toContain("--accent-ring: rgba(97, 175, 239, .4);");
    expect(styles).toContain("--radius-xs: 4px;");
    expect(styles).toContain("--radius-sm: 6px;");
    expect(styles).toContain("--radius: 8px;");
  });

  it("показывает контур у неакцентных кнопок", () => {
    expect(styles).toMatch(/button\.ghost \{[^}]*border: 1px solid var\(--border-strong\);/);
    expect(styles).toMatch(/button\.ghost:hover \{[^}]*border-color: var\(--accent\);/);
  });

  it("сжимает три поля настроек до одной колонки на очень узком экране", () => {
    expect(styles).toMatch(/@media \(max-width: 480px\)\s*\{[\s\S]*?\.set-cols3 \{ grid-template-columns: minmax\(0, 1fr\); \}/);
    expect(styles).toMatch(/@media \(max-width: 900px\)\s*\{[\s\S]*?\.set-cols3 \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); \}/);
  });

  it("позволяет карточке Settings сжаться как прямому grid item на 320px", () => {
    expect(styles).toMatch(/\.set-card \{[^}]*min-width: 0;/);
  });

  it("использует логические свойства для RTL-зеркалирования", () => {
    expect(styles).not.toMatch(/^\s*(?:margin|padding)-(?:left|right)\s*:/m);
    expect(styles).not.toMatch(/^\s*(?:left|right)\s*:/m);
    expect(styles).not.toMatch(/^\s*text-align:\s*(?:left|right)\s*;/m);
  });

  it("держит мобильный контент и bottom-sheet внутри 16px inline inset", () => {
    expect(styles).toMatch(/@media \(max-width: 600px\)\s*\{[\s\S]*?#view \{ padding: calc\(14px \+ env\(safe-area-inset-top\)\) 16px/);
    expect(styles).toContain(".modal { width: calc(100% - 32px);");
    expect(styles).toContain("margin: 0 16px var(--tabbar-h);");
  });

  it("вычисляет нижние отступы фиксированных элементов через общие переменные", () => {
    expect(styles).toContain("--bottom-ui-offset: calc(var(--tabbar-h) + var(--player-h));");
    expect(styles).toContain("bottom: calc(var(--bottom-ui-offset) + var(--selbar-gap));");
    expect(styles).toContain("bottom: calc(var(--bottom-ui-offset) + var(--dock-gap) + var(--dock-player-gap));");
  });

  it("центрирует cmdk и selbar независимо от направления письма", () => {
    expect(styles).toMatch(/\.cmdk \{[^}]*inset-inline: 0;[^}]*margin-inline: auto/);
    expect(styles).toMatch(/\.selbar \{[^}]*inset-inline: 0;[^}]*margin-inline: auto/);
    expect(styles).not.toMatch(/\.cmdk \{[^}]*translateX\(-50%\)/);
    expect(styles).not.toMatch(/\.selbar \{[^}]*translateX\(-50%\)/);
  });

  it("на 320px раскладывает вкладки библиотеки в две колонки без разрыва слов", () => {
    expect(styles).not.toMatch(/\.library-view-tabs button \{[^}]*text-overflow: ellipsis/);
    expect(styles).not.toMatch(/\.library-view-tabs button \{[^}]*overflow-wrap: anywhere/);
    expect(styles).toMatch(/@media \(max-width: 360px\)\s*\{[\s\S]*?\.library-view-tabs \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); \}/);
    expect(styles).toMatch(/@media \(max-width: 360px\)\s*\{[\s\S]*?\.library-view-tabs button \{[^}]*white-space: nowrap;/);
  });

  it("не ограничивает двухрядные вкладки высотой сегмента", () => {
    expect(styles).toMatch(/\.library-view-tabs \{[^}]*height: auto;/);
  });

  it("не применяет hover-эффект к disabled-кнопке", () => {
    expect(styles).toMatch(/button:disabled:hover, \.btn:disabled:hover \{ filter: none; \}/);
  });

  it("даёт сегментам touch-цель не меньше 44px на coarse-указателе", () => {
    expect(styles).toMatch(/@media \(pointer: coarse\)\s*\{[\s\S]*?\.seg:not\(\.library-view-tabs\) \{[^}]*height: calc\(var\(--tap-min\) \+ 4px\);/);
    expect(styles).toMatch(/@media \(pointer: coarse\)\s*\{[\s\S]*?\.seg button \{[^}]*min-height: var\(--tap-min\);/);
  });
});

describe("Zed palette contrast", () => {
  it("keeps primary text, muted text, and accent readable in dark mode", () => {
    expect(contrast("#C8CCD4", "#191919")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#ABB2BF", "#191919")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#61AFEF", "#191919")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#17191D", "#61AFEF")).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps primary text, muted text, and accent readable in light mode", () => {
    expect(contrast("#343B46", "#F5F7FA")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#5B6472", "#F5F7FA")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#2A6FB8", "#F5F7FA")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#FFFFFF", "#2A6FB8")).toBeGreaterThanOrEqual(4.5);
  });
});
