import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MenuScreen from "../src/views/MenuScreen";

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

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

beforeEach(() => {
  location.hash = "";
  vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(HOME)));
});

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = "";
});

describe("MenuScreen", () => {
  it("статистика, недавние треки, здоровье, Shazam", async () => {
    const user = userEvent.setup();
    render(<MenuScreen />);
    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());
    expect(screen.getByText("Треки")).toBeInTheDocument();
    expect(screen.getByText("1:00:00")).toBeInTheDocument(); // длительность

    // Недавний трек → deep-link в библиотеку.
    await user.click(screen.getByText("Кино — Группа крови"));
    expect(location.hash).toBe("#/library?path=" + encodeURIComponent("/lib/Кино/Группа крови/01.mp3"));

    // Здоровье: проблемы и переход в «Проблемы».
    expect(screen.getByText("Проблем: 2")).toBeInTheDocument();
    await user.click(screen.getByText("Здоровье"));
    expect(location.hash).toBe("#/quality");

    // Shazam: счётчик очереди и переход на таб.
    expect(screen.getByText("В очереди: 3")).toBeInTheDocument();
    await user.click(screen.getByText("Shazam"));
    expect(location.hash).toBe("#/discover/shazam");
  });

  it("статистика: жанры/исполнители переключаются", async () => {
    const user = userEvent.setup();
    render(<MenuScreen />);
    await waitFor(() => expect(screen.getByText("Рок")).toBeInTheDocument());
    expect(screen.getByText("8 · 66.7%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Исполнители" }));
    expect(screen.getByText("Кино")).toBeInTheDocument();
    expect(screen.queryByText("Рок")).not.toBeInTheDocument();
  });

  it("нижние панели являются keyboard-reachable ссылками", async () => {
    render(<MenuScreen />);
    await waitFor(() => expect(screen.getByText("Здоровье")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Здоровье/ })).toHaveAttribute("href", "#/quality");
    expect(screen.getByRole("link", { name: /Shazam/ })).toHaveAttribute("href", "#/discover/shazam");
  });

  it("ошибка /api/home — панель с ошибкой", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "нет библиотеки" }, 500)));
    render(<MenuScreen />);
    await waitFor(() => expect(screen.getByText("Ошибка: нет библиотеки")).toBeInTheDocument());
  });

  it("кнопки героя ведут на поиск и проблемы", async () => {
    const user = userEvent.setup();
    render(<MenuScreen />);
    await user.click(screen.getByRole("button", { name: "Найти музыку" }));
    expect(location.hash).toBe("#/discover/search");
    await user.click(screen.getByRole("button", { name: "Навести порядок" }));
    expect(location.hash).toBe("#/quality");
  });

  /* Регрессия скелетона главной: секции HomeBody (чипы статистики,
     home-cols, нижние карточки), не общие строки SkeletonRows —
     подробные проверки в menuSkeleton.test.tsx. */
  it("во время загрузки — скелетон секций главной", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    render(<MenuScreen />);
    expect(document.querySelector(".menu-home > .menu-skeleton")).toBeTruthy();
    expect(document.querySelector(".trackrow")).toBeNull();
    expect(document.querySelector(".lib-skeleton")).toBeNull();
  });
});
