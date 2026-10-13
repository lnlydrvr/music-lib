import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SkeletonRows } from "../src/components/ui/SkeletonRows";

/* Скелетон строк должен зеркалить TrackRow/PlaylistRow: обложка 48 +
   title/sub (+ опционально мета-колонка справа). */
describe("SkeletonRows", () => {
  it("по умолчанию — обложка и title/sub, без мета-колонки", () => {
    const { container } = render(<SkeletonRows n={1} />);
    const row = container.querySelector(".trackrow")!;
    expect(row).toBeTruthy();
    expect(row.getAttribute("aria-hidden")).toBe("true");
    expect(row.querySelector(".skeleton[style*='48']")).toBeTruthy();
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(3);
    expect(row.querySelector(".t-meta")).toBeNull();
  });

  it("meta: добавляет справа .t-meta с полосой — зеркало TrackRow/PlaylistRow", () => {
    const { container } = render(<SkeletonRows n={2} meta />);
    const rows = container.querySelectorAll(".trackrow");
    expect(rows).toHaveLength(2);
    rows.forEach((r) => {
      const meta = r.querySelector(".t-meta");
      expect(meta).toBeTruthy();
      expect(meta!.querySelector(".skeleton")).toBeTruthy();
    });
  });
});
