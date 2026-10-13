import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import LibraryScreen from "../src/views/LibraryScreen";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

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
];

/* Вкладка «Плейлисты» грузит YT-плейлисты отдельно от библиотеки:
   после начальной загрузки при переключении на вкладку не должно быть
   пустоты — скелетон строк (как PlaylistRow), пока ответ в полёте. */
describe("PlaylistsTab: загрузка YT-плейлистов", () => {
  let playlistResponse: unknown[] | null;
  let accountConnected: boolean;

  beforeEach(() => {
    playlistResponse = null;
    accountConnected = true;
    Element.prototype.scrollIntoView = vi.fn();
    location.hash = "#/library";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/library?")) return jsonResponse(TRACKS);
        if (url.startsWith("/api/library/inbox")) return jsonResponse([]);
        if (url === "/api/settings") return jsonResponse({});
        /* Подключённый аккаунт: альбомы/артисты отвечают (пусто), а
           плейлисты — висят: только этот запрос в полёте. */
        if (url.startsWith("/api/ytmusic/albums")) {
          if (!accountConnected) return jsonResponse({ error: "not connected" }, 503);
          return jsonResponse({ albums: [] });
        }
        if (url.startsWith("/api/ytmusic/artists")) {
          if (!accountConnected) return jsonResponse({ error: "not connected" }, 503);
          return jsonResponse({ artists: [] });
        }
        if (url.startsWith("/api/ytmusic/playlists")) {
          return playlistResponse === null
            ? new Promise<Response>(() => {})
            : jsonResponse({ playlists: playlistResponse });
        }
        throw new Error(`unexpected ${url}`);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    location.hash = "";
  });

  it("пока плейлисты грузятся — скелетон строк, не пустота", async () => {
    const user = userEvent.setup();
    render(
      <DialogProvider>
        <LibraryScreen />
      </DialogProvider>,
    );
    // Ждём конца загрузки библиотеки (скелетон экрана скрылся).
    await screen.findByText(/1 альбом/);

    await user.click(screen.getByRole("button", { name: "Плейлисты" }));

    // Скелетон вкладки: строки-заглушки, а не пустое место и не экран загрузки.
    expect(document.querySelector(".lib-skeleton")).toBeNull();
    const rows = document.querySelectorAll(".trackrow[aria-hidden='true']");
    expect(rows.length).toBeGreaterThanOrEqual(3);
    rows.forEach((r) => {
      expect(r.querySelector(".skeleton[style*='48']")).toBeTruthy();
      expect(r.querySelector(".t-main .skeleton")).toBeTruthy();
    });
    // Ответ ещё не пришёл: ни «плейлистов нет», ни «не подключён».
    expect(screen.queryByText("Плейлистов не сохранено")).toBeNull();
    expect(screen.queryByText(/YouTube Music не подключён/)).toBeNull();
  });

  it.each([
    [true, "library.playlists.none"],
    [false, "library.playlists.disconnected"],
  ])("показывает %s empty state для пустого списка", async (connected, key) => {
    accountConnected = connected;
    playlistResponse = [];
    const user = userEvent.setup();
    render(
      <DialogProvider>
        <LibraryScreen />
      </DialogProvider>,
    );
    await screen.findByText(/1 альбом/);
    await user.click(screen.getByRole("button", { name: "Плейлисты" }));
    await screen.findByText(
      key === "library.playlists.none"
        ? "Плейлистов не сохранено"
        : "YouTube Music не подключён: подключите в «Настройках»",
    );
  });
});
