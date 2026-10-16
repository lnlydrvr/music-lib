import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import DiscoverScreen from "../src/views/DiscoverScreen";
import SearchScreen from "../src/views/SearchScreen";
import { startJob } from "../src/lib/jobs";
import { runMetaflow } from "../src/features/editor";
import { resetYtmSettings } from "../src/features/ytm/settings";
import { toast } from "../src/lib/toast";
import type { RenderableMessage } from "../src/i18n/messages";
import { changeLanguage } from "../src/i18n";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));
vi.mock("../src/lib/jobs", () => ({ startJob: vi.fn() }));
vi.mock("../src/features/editor", () => ({ runMetaflow: vi.fn(async () => true) }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const TRACK = {
  video_id: "vid1",
  title: "Found Song",
  artist: "Found Artist",
  album: "Album",
  year: 2021,
  cover_url: "http://c/1.jpg",
  duration: 123,
  video_type: "MUSIC_VIDEO_TYPE_ATV",
  in_library: false,
};

function makeFetch(settings: Record<string, unknown> = {}) {
  return vi.fn(async (url: string) => {
    if (url === "/api/settings") {
      return jsonResponse({ search_source: "youtube_music", ytmusic_connected: true, ...settings });
    }
    if (url.startsWith("/api/ytmusic/search")) return jsonResponse({ tracks: [TRACK] });
    if (url.startsWith("/api/search")) {
      return jsonResponse([{ id: "y1", title: "YT Song", uploader: "Chan", duration: 200, url: "http://w/1", thumbnail: "http://t/1.jpg" }]);
    }
    throw new Error(`unexpected ${url}`);
  });
}

beforeEach(() => {
  resetYtmSettings();
  vi.mocked(toast).mockClear();
  vi.mocked(startJob).mockReset();
  vi.mocked(runMetaflow).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SearchScreen", () => {
  it("rerenders search chrome on locale change without translating a result", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch());
    render(<DialogProvider><SearchScreen /></DialogProvider>);
    await user.type(screen.getByLabelText("Запрос на YouTube или URL"), "query");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Результаты (YouTube Music): query")).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });

    expect(screen.getByRole("heading", { name: "Search & download" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Results (YouTube Music): query" })).toBeInTheDocument();
    expect(screen.getByText("Tags come from YouTube Music (album and cover); downloads use the format from Settings; metadata from iTunes/Deezer can be offered afterwards.")).toBeInTheDocument();
    expect(screen.getByText("Found Artist")).toBeInTheDocument();
  });
  it("стартовый источник — YouTube Music из настроек; поиск рендерит строки", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch());
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "YouTube Music" }).getAttribute("aria-pressed")).toBe("true"),
    );

    await user.type(screen.getByLabelText("Запрос на YouTube или URL"), "запрос");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Результаты (YouTube Music): запрос")).toBeInTheDocument();
    expect(screen.getByText("Found Artist")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Прослушать: Found Song" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скачать: Found Song" })).toBeInTheDocument();
  });

  it("скачивание YTM: job /api/ytmusic/download с настройками; после — метафлоу и «в библиотеке»", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch({ default_format: "mp3", default_quality: 320, ytmusic_no_clips: true }));
    vi.mocked(startJob).mockResolvedValue({
      ok: 1,
      errors: 0,
      archive: "/lib/Плейлисты/YouTube Music.m3u8",
      items: [{ video_id: "vid1", ok: true, path: "/lib/Found Artist/Found Song.mp3" }],
    } as never);
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "запрос");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await screen.findByText("Результаты (YouTube Music): запрос");

    await user.click(screen.getByRole("button", { name: "Скачать: Found Song" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledTimes(1));
    const [endpoint, body] = vi.mocked(startJob).mock.calls[0];
    expect(endpoint).toBe("/api/ytmusic/download");
    expect(body).toMatchObject({
      playlist: "ytm-track-vid1",
      fmt: "mp3",
      quality: 320,
      move: true,
      no_clips: true,
      items: [expect.objectContaining({ video_id: "vid1", album_artist: "Found Artist" })],
    });

    // Тост об архиве + предложение метаданных (пропускаем) → runMetaflow не звался.
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ code: "ytm.download.archive", params: { name: "YouTube Music.m3u8" } }));
    await user.click(screen.getByRole("button", { name: "Пропустить" }));
    await waitFor(() => expect(screen.getByText("в библиотеке")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Скачать: Found Song" })).not.toBeInTheDocument();
    expect(runMetaflow).not.toHaveBeenCalled();
  });

  it("метафлоу по согласию: runMetaflow с путём и обложкой", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch());
    vi.mocked(startJob).mockResolvedValue({
      ok: 1,
      errors: 0,
      items: [{ video_id: "vid1", ok: true, path: "/lib/song.m4a" }],
    } as never);
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "запрос");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await screen.findByText("Результаты (YouTube Music): запрос");

    await user.click(screen.getByRole("button", { name: "Скачать: Found Song" }));
    await user.click(await screen.findByRole("button", { name: "Да" }));
    await waitFor(() =>
      expect(runMetaflow).toHaveBeenCalledWith("/lib/song.m4a", "http://c/1.jpg", expect.any(Function)),
    );
    await waitFor(() => expect(screen.getByText("в библиотеке")).toBeInTheDocument());
  });

  it.each<[string, RenderableMessage]>([
    ["known descriptor", { code: "jobs.download.failed", params: { retryAfter: 30 }, message: "Download error" }],
    ["legacy string", "Provider download failed"],
  ])("скачивание YTM передаёт %s result error в toast без потери значения", async (_kind, error) => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch());
    vi.mocked(startJob).mockResolvedValue({
      ok: 0,
      errors: 1,
      items: [{ video_id: "vid1", ok: false, error }],
    } as never);
    render(<DialogProvider><SearchScreen /></DialogProvider>);
    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "запрос");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Found Song" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith(error, "error"));
  });

  it("сегмент YouTube: обычный поиск и запуск /api/download", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ search_source: "youtube", ytmusic_connected: true });
        if (url.startsWith("/api/search")) {
          return jsonResponse([{ id: "y1", title: "YT Song", uploader: "Chan", duration: 200, url: "http://w/1", thumbnail: "http://t/1.jpg" }]);
        }
        if (url === "/api/library/move") return jsonResponse({ to: "/lib/YT Song.m4a" });
        throw new Error(`unexpected ${url}`);
      }),
    );
    vi.mocked(startJob).mockResolvedValue({ filepath: "/lib/yt.mp3", info: {} } as never);
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "YouTube" }).getAttribute("aria-pressed")).toBe("true"),
    );
    await user.type(screen.getByLabelText("Запрос на YouTube или URL"), "песня");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Результаты: песня")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Скачать: YT Song" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledWith("/api/download", { url: "http://w/1", move: false }, expect.anything()));
    await user.click(await screen.findByRole("button", { name: "Пропустить" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ code: "search.metaflow.added_to_library" }));
  });

  it("обычное скачивание показывает canonical structured message без legacy msg", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch({ search_source: "youtube" }));
    vi.mocked(startJob).mockImplementationOnce(((_endpoint, _body, options) => {
      options?.onProgress?.({
        percent: 25,
        message: { code: "jobs.download.bytes", params: { sizeMb: "7.5" }, message: "Downloading… 7.5 MB" },
      });
      return new Promise(() => {});
    }) as typeof startJob);
    render(<DialogProvider><SearchScreen /></DialogProvider>);

    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "https://youtube.example/watch?v=1");
    await user.keyboard("{Enter}");

    expect(await screen.findByText("Скачивание... 7.5 МБ")).toBeInTheDocument();
  });

  it("сохраняет дескрипторы этапов операции и переводит уже открытую панель", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch({ search_source: "youtube" }));
    vi.mocked(startJob).mockImplementationOnce(((_endpoint, _body, options) => {
      options?.onProgress?.({ percent: 25, message: { code: "jobs.download.bytes", params: { sizeMb: "7.5" } } });
      return new Promise(() => {});
    }) as typeof startJob);
    render(<DialogProvider><SearchScreen /></DialogProvider>);

    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "https://youtube.example/watch?v=1");
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("listitem", { name: "Скачать: выполняется" })).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });

    expect(screen.getByRole("listitem", { name: "Download: running" })).toBeInTheDocument();
  });

  it("провальный поиск — панель с повтором", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ search_source: "youtube" });
        if (url.startsWith("/api/search")) return jsonResponse({ detail: "сеть отвалилась" }, 502);
        throw new Error(`unexpected ${url}`);
      }),
    );
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "песня");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Поиск не удался: сеть отвалилась")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Попробовать снова" })).toBeInTheDocument();
  });

  /* Новый запрос: прежние результаты и заголовок скрываются сразу (модель
     данных не меняется), а на их месте — скелетон строк результата, не
     текстовая строка «Поиск...». */
  it("новый поиск: скелетон строк, прежние результаты скрыты", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ search_source: "youtube" });
        if (url.startsWith("/api/search")) {
          const q = new URLSearchParams(url.split("?")[1]).get("q");
          if (q === "песня") {
            return jsonResponse([{ id: "y1", title: "Первая песня", uploader: "Chan", duration: 100, url: "http://w/1", thumbnail: "" }]);
          }
          return new Promise<Response>(() => {}); // второй запрос завис
        }
        throw new Error(`unexpected ${url}`);
      }),
    );
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    const input = await screen.findByLabelText("Запрос на YouTube или URL");
    await user.type(input, "песня");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Первая песня")).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "вторая");
    await user.keyboard("{Enter}");

    // Скелетон строк результата (обложка + title/sub + мета), не текст.
    const rows = document.querySelectorAll(".trackrow[aria-hidden='true']");
    expect(rows.length).toBeGreaterThanOrEqual(5);
    rows.forEach((r) => {
      expect(r.querySelector(".skeleton[style*='48']")).toBeTruthy();
      expect(r.querySelector(".t-meta .skeleton")).toBeTruthy();
    });
    // Прежний заголовок/строки скрыты сразу, текстовой загрузки нет.
    expect(screen.queryByText("Результаты: песня")).toBeNull();
    expect(screen.queryByText("Первая песня")).toBeNull();
    expect(screen.queryByText("Поиск...")).toBeNull();
  });

  /* Регрессия модели догрузки: «Показать ещё» дописывает только хвост
     ответа — прежние строки остаются, дублей нет. */
  it("«Показать ещё»: хвост добавляется к прежним результатам без дублей", async () => {
    const user = userEvent.setup();
    const gen = (n: number) =>
      Array.from({ length: n }, (_, i) => ({
        id: `y${i}`, title: `Песня ${i + 1}`, uploader: "Chan", duration: 100 + i, url: `http://w/${i}`, thumbnail: "",
      }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ search_source: "youtube" });
        if (url.startsWith("/api/search")) {
          const limit = Number(new URLSearchParams(url.split("?")[1]).get("limit"));
          return jsonResponse(gen(Math.min(limit, 14))); // сервер не пагинирует: 10, потом 14
        }
        throw new Error(`unexpected ${url}`);
      }),
    );
    render(
      <DialogProvider>
        <SearchScreen />
      </DialogProvider>,
    );
    await user.type(await screen.findByLabelText("Запрос на YouTube или URL"), "песня");
    await user.keyboard("{Enter}");
    expect(await screen.findAllByText(/Песня \d+/)).toHaveLength(10);

    await user.click(screen.getByRole("button", { name: "Показать ещё 10 (показано 10)" }));
    const titles = (await screen.findAllByText(/Песня \d+/)).map((t) => t.textContent);
    expect(titles).toHaveLength(14);
    expect(new Set(titles).size).toBe(14); // без дублей первых 10
    // 14 < запрошенных 20 — кнопки «Показать ещё» больше нет.
    await waitFor(() => expect(screen.queryByRole("button", { name: /Показать ещё/ })).toBeNull());
  });

  it.each([
    ["en", 1, "Playlist (1 track)"],
    ["en", 2, "Playlist (2 tracks)"],
    ["ru", 1, "Плейлист (1 трек)"],
    ["ru", 2, "Плейлист (2 трека)"],
    ["ru", 5, "Плейлист (5 треков)"],
  ] as const)("renders playlist count using ICU pluralization in %s for %i entries", async (locale, count, heading) => {
    await changeLanguage(locale);
    const user = userEvent.setup();
    const entries = Array.from({ length: count }, (_, index) => ({
      index: index + 1,
      id: `video-${index}`,
      title: `Track ${index + 1}`,
      uploader: "Artist",
      duration: 120,
      url: `https://youtube.example/watch?v=${index}`,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ search_source: "youtube" });
        if (url.startsWith("/api/playlist")) return jsonResponse(entries);
        throw new Error(`unexpected ${url}`);
      }),
    );
    render(<DialogProvider><SearchScreen /></DialogProvider>);

    await user.type(await screen.findByLabelText(locale === "ru" ? "Запрос на YouTube или URL" : "YouTube query or URL"), "https://youtube.example/playlist?list=1");
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});

describe("DiscoverScreen", () => {
  it("табы Поиск/Shazam: активация, ленивый маунт и hash", async () => {
    const user = userEvent.setup();
    location.hash = "#/discover";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ search_source: "youtube" });
        if (url === "/api/shazam/scan") return jsonResponse({ job_id: "j1" });
        throw new Error(`unexpected ${url}`);
      }),
    );
    vi.mocked(startJob).mockRejectedValue(new Error("Файл Shazam не задан или не найден — укажите путь в настройках") as never);
    render(
      <DialogProvider>
        <DiscoverScreen />
      </DialogProvider>,
    );

    // Поиск смонтирован сразу, Shazam — лениво.
    expect(screen.getByRole("heading", { name: "Поиск и скачивание" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Shazam" })).not.toBeInTheDocument();

    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Поиск", "Shazam", "Lucida"]);
    await user.click(screen.getByRole("tab", { name: "Shazam" }));
    expect(location.hash).toBe("#/discover/shazam");
    expect(await screen.findByRole("heading", { name: "Shazam" })).toBeInTheDocument();
    // Панель поиска осталась смонтированной (состояние сохраняется), но скрыта.
    expect(screen.getByRole("heading", { name: "Поиск и скачивание", hidden: true })).toBeInTheDocument();

    // Сканирование стартует автоматически; файл не настроен — подсказка.
    expect(await screen.findByText("Файл Shazam не задан или не найден — укажите путь в настройках")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Открыть настройки" })).not.toBeInTheDocument();
  });
});
