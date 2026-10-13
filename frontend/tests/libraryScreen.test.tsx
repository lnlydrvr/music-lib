import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import LibraryScreen from "../src/views/LibraryScreen";
import { toast } from "../src/lib/toast";
import { startJob } from "../src/lib/jobs";
import i18n, { changeLanguage } from "../src/i18n";

const { findAlbumTwin, ytData } = vi.hoisted(() => ({
  findAlbumTwin: vi.fn(async () => null),
  ytData: vi.fn(async () => []),
}));

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));
vi.mock("../src/lib/jobs", () => ({ startJob: vi.fn() }));
vi.mock("../src/views/library/useYtData", () => ({
  useYtData: () => ({
    ytData,
    findAlbumTwin,
    ytArtistAlbums: vi.fn(async () => []),
    refreshAfterYtDownload: vi.fn(async () => {}),
    connected: true,
    epoch: 0,
  }),
}));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const TRACKS = [
  {
    path: "/lib/Artist X/Song One.mp3", title: "Song One", artist: "Artist X", album: "Album X",
    year: "2020", genre: "Rock", album_artist: "Artist X", isrc: "", composer: "",
    track_number: "1", disc_number: "1", size_bytes: 1000, duration_seconds: 100, bitrate: 320,
    mtime: 1700000000, has_lyrics: true, has_synced_lyrics: true, has_cover: true, ext: ".mp3",
  },
  {
    path: "/lib/Artist X/Song Two.mp3", title: "Song Two", artist: "Artist X", album: "Album X",
    year: "2020", genre: "Rock", album_artist: "Artist X", isrc: "", composer: "",
    track_number: "2", disc_number: "1", size_bytes: 2000, duration_seconds: 200, bitrate: 320,
    mtime: 1700000001, has_lyrics: false, has_synced_lyrics: false, has_cover: false, ext: ".mp3",
  },
];

beforeEach(() => {
  findAlbumTwin.mockClear();
  ytData.mockClear();
  Element.prototype.scrollIntoView = vi.fn();
  vi.mocked(startJob).mockResolvedValue({ updated: 1, skipped: 0, errors: 0 } as never);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.startsWith("/api/library?")) return jsonResponse(TRACKS);
      if (url.startsWith("/api/library/inbox")) return jsonResponse([]);
      if (url === "/api/settings") return jsonResponse({ name_translit: "auto" });
      if (url === "/api/lyrics/missing") return jsonResponse({ snapshot: ["/lib/Artist X/Song Two.mp3"] });
      if (url.startsWith("/api/ytmusic/")) return jsonResponse({ detail: "не подключён" }, 502);
      throw new Error(`unexpected ${url}`);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = "";
  void changeLanguage("ru");
});

function renderScreen() {
  return render(
    <DialogProvider>
      <LibraryScreen />
    </DialogProvider>,
  );
}

describe("LibraryScreen deep-link ?path=", () => {
  it("rerenders library-owned copy on a locale switch without changing music metadata", async () => {
    await changeLanguage("en");
    renderScreen();

    expect(await screen.findByRole("heading", { name: "Library" })).toBeInTheDocument();
    expect(screen.getAllByText("Album X").length).toBeGreaterThan(0);

    await changeLanguage("ru");

    expect(await screen.findByRole("heading", { name: "Библиотека" })).toBeInTheDocument();
    expect(screen.getAllByText("Album X").length).toBeGreaterThan(0);
  });

  it("rebuilds artist-page local album groups when the active locale changes", async () => {
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Исполнители" }));
    await userEvent.click(await screen.findByRole("button", { name: /Исполнитель: Artist X/ }));
    await waitFor(() => expect(ytData).toHaveBeenCalledWith("albums"));
    const callsBeforeLocaleChange = ytData.mock.calls.length;

    await act(() => changeLanguage("en"));

    await waitFor(() => expect(ytData.mock.calls.length).toBeGreaterThan(callsBeforeLocaleChange));
  });

  it("открывает вкладку «Треки», подсвечивает карточку и панель деталей", async () => {
    location.hash = "#/library?path=" + encodeURIComponent("/lib/Artist X/Song Two.mp3");
    renderScreen();

    // Deep-link переключает на «Треки».
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Треки" }).getAttribute("aria-pressed")).toBe("true"),
    );
    // Карточка целевого трека подсвечена.
    await waitFor(() => {
      const card = document.querySelector('.lib-card[data-path="/lib/Artist X/Song Two.mp3"]');
      expect(card).toBeTruthy();
      expect(card!.className).toContain("active");
    });
    // Панель деталей справа — поля трека (карточка + панель = 2 вхождения).
    expect(screen.getByText("Информация")).toBeInTheDocument();
    expect(screen.getByText("Название:")).toBeInTheDocument();
    expect(screen.getAllByText("Song Two").length).toBe(2);
    expect(screen.getByText("320 kbps")).toBeInTheDocument();
    // Счётчик библиотеки в тулбаре.
    await waitFor(() => expect(screen.getByText(/2 трека/)).toBeInTheDocument());
  });

  it("вкладка «Альбомы» по умолчанию: группировка треков в альбом", async () => {
    location.hash = "#/library";
    renderScreen();
    const card = await screen.findByRole("button", { name: /Открыть альбом: Album X — Artist X \(2 из 2 тр\.\)/ });
    expect(card).toBeInTheDocument();
    // Панель деталей трека не открыта.
    expect(screen.queryByText("Информация")).not.toBeInTheDocument();
    void toast;
  });

  it("помечает ряд представлений библиотеки отдельной группой", async () => {
    renderScreen();

    const tabs = await screen.findByRole("group", { name: "Представления библиотеки" });
    expect(tabs).toHaveClass("library-view-tabs");
    expect(within(tabs).getAllByRole("button")).toHaveLength(4);
  });

  it("показывает только поддерживаемые сортировки", async () => {
    renderScreen();
    const sort = await screen.findByRole("combobox", { name: "Сортировка треков" });
    expect(within(sort).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "По названию",
      "По исполнителю",
      "По размеру",
    ]);
  });
});

describe("LibraryScreen обновление текстов", () => {
  it("передаёт snapshot после подтверждения и показывает фазу подготовки", async () => {
    const user = userEvent.setup();
    let resolveSnapshot: (() => void) | undefined;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/lyrics/missing") {
        return new Promise<Response>((resolve) => {
          resolveSnapshot = () => resolve(jsonResponse({ snapshot: ["/lib/Artist X/Song Two.mp3"] }) as Response);
        });
      }
      if (url.startsWith("/api/library?")) return jsonResponse(TRACKS);
      if (url.startsWith("/api/library/inbox")) return jsonResponse([]);
      if (url === "/api/settings") return jsonResponse({ name_translit: "auto" });
      if (url.startsWith("/api/ytmusic/")) return jsonResponse({ detail: "не подключён" }, 502);
      throw new Error(`unexpected ${url}`);
    }));
    renderScreen();

    await screen.findByRole("button", { name: /Открыть альбом: Album X/ });
    await user.click(screen.getByRole("button", { name: "Обновить тексты песен" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Обновить" }));

    expect(screen.getByText("Подготавливаем список текстов…")).toBeInTheDocument();
    resolveSnapshot?.();
    await waitFor(() => expect(startJob).toHaveBeenCalledWith(
      "/api/lyrics/update-all",
      { snapshot: ["/lib/Artist X/Song Two.mp3"] },
      expect.anything(),
    ));
  });

  it("запускает обновление без snapshot, если его запрос завершился ошибкой", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/lyrics/missing") throw new Error("snapshot недоступен");
      if (url.startsWith("/api/library?")) return jsonResponse(TRACKS);
      if (url.startsWith("/api/library/inbox")) return jsonResponse([]);
      if (url === "/api/settings") return jsonResponse({ name_translit: "auto" });
      if (url.startsWith("/api/ytmusic/")) return jsonResponse({ detail: "не подключён" }, 502);
      throw new Error(`unexpected ${url}`);
    }));
    renderScreen();

    await screen.findByRole("button", { name: /Открыть альбом: Album X/ });
    await user.click(screen.getByRole("button", { name: "Обновить тексты песен" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Обновить" }));

    await waitFor(() => expect(startJob).toHaveBeenCalledWith(
      "/api/lyrics/update-all",
      {},
      expect.anything(),
    ));
  });
});
