import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import MiscScreen from "../src/views/MiscScreen";
import { startJob } from "../src/lib/jobs";
import { runMetaflow } from "../src/features/editor";
import { toast } from "../src/lib/toast";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));
vi.mock("../src/lib/jobs", () => ({ startJob: vi.fn() }));
vi.mock("../src/features/editor", () => ({ runMetaflow: vi.fn(async () => true) }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const SCAN = {
  file: "/shazam/Название - Исполнитель.txt",
  entries: [
    {
      index: 1,
      line_number: 4,
      title: "Song",
      artist: "Artist",
      display: "Song - Artist",
      found: [
        { id: "h1", title: "Song", uploader: "Artist - Topic", duration: 180, url: "http://w/h1", cover_url: "", score: 0.92 },
      ],
    },
    { index: 2, line_number: 5, title: "Empty", artist: "X", display: "Empty - X", found: [] },
  ],
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  location.hash = "";
  vi.mocked(toast).mockClear();
  vi.mocked(startJob).mockReset();
  vi.mocked(runMetaflow).mockClear();
  fetchMock = vi.fn(async () => jsonResponse({}));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = "";
});

describe("MiscScreen (Shazam)", () => {
  it("скан: файл, группы-строки, совпадение и пустой результат", async () => {
    vi.mocked(startJob).mockResolvedValue(SCAN as never);
    render(
      <DialogProvider>
        <MiscScreen />
      </DialogProvider>,
    );
    expect(await screen.findByText("Файл: /shazam/Название - Исполнитель.txt")).toBeInTheDocument();
    expect(screen.getByText("Song - Artist")).toBeInTheDocument();
    expect(screen.getByText("Empty - X")).toBeInTheDocument();
    expect(screen.getByText("Совпадений в YouTube Music не найдено")).toBeInTheDocument();
    expect(screen.getByText("3:00 · совпадение 92%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Удалить строку: Song - Artist" })).toBeInTheDocument();
  });

  it("передаёт descriptor из message в прогресс сканирования", async () => {
    vi.mocked(startJob).mockImplementation(async (_endpoint, _body, options) => {
      options?.onProgress?.({ percent: 50, message: { code: "jobs.shazam.scanning", params: { count: 2 } } });
      return SCAN as never;
    });
    render(
      <DialogProvider>
        <MiscScreen />
      </DialogProvider>,
    );

    expect(await screen.findByText("Поиск 2 треков в YouTube Music…")).toBeInTheDocument();
  });

  it("передаёт descriptor из message в прогресс скачивания", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockImplementation(async (endpoint, _body, options) => {
      if (endpoint === "/api/download") {
        options?.onProgress?.({ percent: 25, message: { code: "jobs.download.bytes", params: { sizeMb: 25 } } });
        return new Promise(() => {}) as never;
      }
      return SCAN as never;
    });
    render(
      <DialogProvider>
        <MiscScreen />
      </DialogProvider>,
    );
    await screen.findByText("Song - Artist");

    await user.click(screen.getByRole("button", { name: "Скачать" }));

    expect(await screen.findByText("Скачивание... 25 МБ")).toBeInTheDocument();
  });

  it("удаление строки: подтверждение → POST /api/shazam/remove → повторный скан", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockResolvedValue(SCAN as never);
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === "/api/shazam/remove") return jsonResponse({ removed: 1 });
      throw new Error(`unexpected ${url}`);
    });
    render(
      <DialogProvider>
        <MiscScreen />
      </DialogProvider>,
    );
    await screen.findByText("Song - Artist");

    await user.click(screen.getByRole("button", { name: "Удалить строку: Song - Artist" }));
    await user.click(screen.getByRole("button", { name: "Удалить" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Удалено строк: 1"));
    const call = fetchMock.mock.calls.find(([u]) => u === "/api/shazam/remove");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ line_number: 4 });
    // После удаления — повторное сканирование.
    await waitFor(() => expect(startJob).toHaveBeenCalledTimes(2));
  });

  it("скачивание совпадения: /api/download → метафлоу (по согласию) → перенос и удаление строки", async () => {
    const user = userEvent.setup();
    vi.mocked(startJob).mockImplementation(async (endpoint: string) => {
      if (endpoint === "/api/download") return { filepath: "/tmp/song.m4a", info: { thumbnail: "http://t/1.jpg" } } as never;
      return SCAN as never;
    });
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/library/move") return jsonResponse({ to: "/lib/Artist/Song/Song.m4a" });
      if (url === "/api/shazam/remove") return jsonResponse({ removed: 1 });
      throw new Error(`unexpected ${url}`);
    });
    render(
      <DialogProvider>
        <MiscScreen />
      </DialogProvider>,
    );
    await screen.findByText("Song - Artist");

    await user.click(screen.getByRole("button", { name: "Скачать" }));
    await user.click(await screen.findByRole("button", { name: "Да" }));
    await waitFor(() =>
      expect(runMetaflow).toHaveBeenCalledWith("/tmp/song.m4a", "http://t/1.jpg", expect.any(Function)),
    );
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Трек добавлен в библиотеку"));
    const remove = fetchMock.mock.calls.find(([u]) => u === "/api/shazam/remove");
    expect(remove).toBeTruthy();
  });
});
