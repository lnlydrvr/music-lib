import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import MenuScreen from "../src/views/MenuScreen";
import { MenuSkeleton } from "../src/views/MenuSkeleton";

/* Регрессия скелетона главной: раньше на время загрузки рисовался общий
   SkeletonRows (две горизонтальные .trackrow), который не соответствовал
   реальной геометрии HomeBody — панель статистики из 5 чипов, .home-cols
   с «Последними добавленными» и «Статистикой», ниже пара карточек
   «Здоровье»/«Shazam». Скелетон должен зеркалить эти секции. */
beforeEach(() => {
  location.hash = "";
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
});

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = "";
});

const HOME = {
  state: { output_dir: "/lib", tracks: 12, artists: 5, albums: 4, duration_seconds: 3600, size_mb: 120.5 },
  genres: [{ name: "Рок", count: 8, pct: 66.7 }],
  artists: [{ name: "Кино", count: 4, pct: 33.3 }],
  recent: [
    { artist: "Кино", title: "Группа крови", album: "Группа крови", ext: ".mp3", mtime: 1700000000, path: "/lib/Кино/Группа крови/01.mp3" },
  ],
  health: { total: 12, issues: 2, counts: { loose: 2 } },
  shazam: { configured: true, count: 3, file: "/shazam.txt" },
};

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

describe("MenuScreen: скелетон главной", () => {
  it("повторяет секции HomeBody: чипы статистики, home-cols, нижние карточки", () => {
    render(<MenuScreen />);

    const sk = document.querySelector(".menu-home > .menu-skeleton");
    expect(sk).toBeTruthy();
    expect(sk!.getAttribute("aria-hidden")).toBe("true");

    // Статистика: панель с 5 чипами (треки/исполнители/альбомы/длительность/размер),
    // каждый — значение + подпись.
    const chips = sk!.querySelectorAll(".sk-chip");
    expect(chips).toHaveLength(5);
    chips.forEach((c) => {
      expect(c.classList.contains("panel")).toBe(true);
      expect(c.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(2);
    });

    // Колонки как у реальной главной: .home-cols (адаптив из styles.css) с двумя панелями.
    const cols = sk!.querySelector(".home-cols");
    expect(cols).toBeTruthy();
    expect(cols!.querySelectorAll(".panel")).toHaveLength(2);

    // «Последние добавленные»: строки-треки — обложка 40, название/альбом, мета справа.
    const recent = cols!.querySelectorAll(".sk-recent-row");
    expect(recent.length).toBeGreaterThanOrEqual(3);
    recent.forEach((r) => {
      expect(r.querySelector(".skeleton[style*='40']")).toBeTruthy();
      expect(r.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(4);
    });

    // «Статистика»: строки как StatRow — точка + имя + счётчик.
    const stats = cols!.querySelectorAll(".sk-stat-row");
    expect(stats.length).toBeGreaterThanOrEqual(4);
    stats.forEach((r) => {
      expect(r.querySelector(".sk-dot")).toBeTruthy();
      expect(r.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(2);
    });

    // Нижняя пара карточек «Здоровье»/«Shazam» в auto-fit-гриде.
    const cards = sk!.querySelectorAll(".sk-cards .sk-card");
    expect(cards).toHaveLength(2);
    cards.forEach((c) => expect(c.querySelectorAll(".skeleton").length).toBeGreaterThanOrEqual(3));

    // Регрессия: раньше — общие две .trackrow (SkeletonRows).
    expect(document.querySelector(".menu-skeleton .trackrow")).toBeNull();
  });

  it("герой и кнопки доступны во время загрузки, скелетон без интерактива", () => {
    render(<MenuScreen />);
    expect(screen.getByRole("button", { name: "Найти музыку" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Навести порядок" })).toBeInTheDocument();
    expect(document.querySelector(".menu-skeleton button")).toBeNull();
  });

  it("после ответа /api/home скелетон сменяется данными", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(HOME)));
    render(<MenuScreen />);
    await waitFor(() => expect(screen.getByText("Треки")).toBeInTheDocument());
    expect(document.querySelector(".menu-skeleton")).toBeNull();
  });
});

describe("MenuSkeleton: компонент", () => {
  it("recent/stats задают число строк, чипов всегда 5", () => {
    const { container } = render(<MenuSkeleton recent={3} stats={4} />);
    const sk = container.querySelector(".menu-skeleton")!;
    expect(sk).toBeTruthy();
    expect(sk.querySelectorAll(".sk-recent-row")).toHaveLength(3);
    expect(sk.querySelectorAll(".sk-stat-row")).toHaveLength(4);
    expect(sk.querySelectorAll(".sk-chip")).toHaveLength(5);
    expect(sk.querySelectorAll(".sk-card")).toHaveLength(2);
  });
});
