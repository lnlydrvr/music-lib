import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import LibraryScreen from "../src/views/LibraryScreen";
import { LibrarySkeleton } from "../src/views/library/LibrarySkeleton";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

/* Загрузка не завершается: экран живёт в состоянии loading —
   скелетон должен повторять сетку/плотность/структуру карточек вкладки. */
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  location.hash = "#/library";
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.removeItem("music-lib-density");
  location.hash = "";
});

function renderScreen() {
  return render(
    <DialogProvider>
      <LibraryScreen />
    </DialogProvider>,
  );
}

describe("LibraryScreen: скелетон библиотеки", () => {
  it("Альбомы (по умолчанию, full): сетка .lib-grid с плотностью и карточками альбомов", () => {
    renderScreen();

    const grid = document.querySelector(".lib-grid.lib-skeleton");
    expect(grid).toBeTruthy();
    expect(grid!.getAttribute("data-density")).toBe("full");

    // Карточки — как LocalAlbumCard/AlbumCard: lib-card album (обложка + title + sub).
    const cards = grid!.querySelectorAll(".lib-card.album");
    expect(cards.length).toBeGreaterThan(0);
    cards.forEach((c) => {
      expect(c.querySelector(".lib-cover")).toBeTruthy();
      expect(c.querySelector(".lib-title .sk-bar")).toBeTruthy();
      expect(c.querySelector(".lib-sub .sk-bar")).toBeTruthy();
    });

    // Регрессия: раньше на вкладке-сетке рисовались горизонтальные .trackrow.
    expect(document.querySelector(".lib-skeleton .trackrow")).toBeNull();
  });

  it("плотность берётся из localStorage (minimal) и доезжает до скелетона", () => {
    localStorage.setItem("music-lib-density", "minimal");
    renderScreen();

    const grid = document.querySelector(".lib-grid.lib-skeleton");
    expect(grid).toBeTruthy();
    expect(grid!.getAttribute("data-density")).toBe("minimal");
  });

  it("вкладка «Треки»: карточки без album — чекбокс, строка, колонки", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.click(screen.getByRole("button", { name: "Треки" }));

    const grid = document.querySelector(".lib-grid.lib-skeleton");
    expect(grid).toBeTruthy();
    const cards = grid!.querySelectorAll(".lib-card");
    expect(cards.length).toBeGreaterThan(0);
    expect(grid!.querySelectorAll(".lib-card.album")).toHaveLength(0);
    cards.forEach((c) => {
      expect(c.querySelector(".lib-check .sk-bar")).toBeTruthy();
      expect(c.querySelector(".lib-rowline .sk-bar")).toBeTruthy();
      // Колонки таблицы «Список»: год/формат/длительность/размер.
      expect(c.querySelectorAll(".lib-cols .sk-bar").length).toBeGreaterThanOrEqual(4);
    });
  });

  it("вкладка «Исполнители»: карточки album (обложка + подпись)", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.click(screen.getByRole("button", { name: "Исполнители" }));

    const grid = document.querySelector(".lib-grid.lib-skeleton");
    expect(grid).toBeTruthy();
    const cards = grid!.querySelectorAll(".lib-card.album");
    expect(cards.length).toBeGreaterThan(0);
    cards.forEach((c) => {
      expect(c.querySelector(".lib-cover")).toBeTruthy();
      expect(c.querySelector(".lib-title .sk-bar")).toBeTruthy();
    });
  });

  it("вкладка «Плейлисты»: строки .trackrow с обложкой 48 и двумя полосами", async () => {
    const user = userEvent.setup();
    renderScreen();
    await user.click(screen.getByRole("button", { name: "Плейлисты" }));

    // Плейлисты и в реальности — строки (PlaylistRow), не сетка.
    expect(document.querySelector(".lib-skeleton .lib-grid")).toBeNull();
    const rows = document.querySelectorAll(".lib-skeleton .trackrow");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((r) => {
      expect(r.querySelector(".cover.cover-48")).toBeTruthy();
      expect(r.querySelector(".t-main .t-title .sk-bar")).toBeTruthy();
      expect(r.querySelector(".t-main .t-sub .sk-bar")).toBeTruthy();
    });
  });
});

describe("LibrarySkeleton: компонент", () => {
  it("n задаёт число заглушек, density подставляется в data-density", () => {
    const { container } = render(<LibrarySkeleton view="albums" density="compact" n={5} />);
    const grid = container.querySelector(".lib-grid.lib-skeleton");
    expect(grid).toBeTruthy();
    expect(grid!.getAttribute("data-density")).toBe("compact");
    expect(grid!.querySelectorAll(".lib-card.album")).toHaveLength(5);
  });

  it("без density — full", () => {
    const { container } = render(<LibrarySkeleton view="tracks" />);
    expect(container.querySelector('.lib-grid[data-density="full"]')).toBeTruthy();
  });
});
