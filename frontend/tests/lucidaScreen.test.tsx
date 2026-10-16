import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LucidaScreen from "../src/views/LucidaScreen";
import { startJob } from "../src/lib/jobs";
import { toast } from "../src/lib/toast";
import { ApiError } from "../src/lib/api";
import { changeLanguage } from "../src/i18n";

vi.mock("../src/lib/jobs", () => ({ startJob: vi.fn() }));
vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

describe("LucidaScreen", () => {
  beforeEach(async () => {
    await changeLanguage("ru");
    vi.mocked(startJob).mockReset();
    vi.mocked(toast).mockClear();
  });

  afterEach(async () => {
    vi.unstubAllGlobals();
    await changeLanguage("en");
  });

  it("explains unavailable access and starts the explicit setup job", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: false, chromium_ready: true, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockResolvedValue({ access_ready: true } as never);

    render(<LucidaScreen />);

    expect(await screen.findByText("Требуется доступ к Lucida. Сначала завершите настройку.")).toBeInTheDocument();
    const search = screen.getByRole("button", { name: "Поиск" });
    expect(search).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Подготовить доступ" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledWith("/api/lucida/setup", {}, expect.anything()));
  });

  it("starts only one setup job while access preparation is pending", async () => {
    const user = userEvent.setup();
    const setup = deferred<{ access_ready: boolean }>();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: false, chromium_ready: true, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockReturnValue(setup.promise as never);

    render(<LucidaScreen />);

    const prepare = await screen.findByRole("button", { name: "Подготовить доступ" });
    await user.click(prepare);
    expect(prepare).toBeDisabled();
    await user.click(prepare);

    expect(startJob).toHaveBeenCalledTimes(1);
    await act(async () => {
      setup.resolve({ access_ready: true });
      await setup.promise;
    });
    await waitFor(() => expect(prepare).toBeEnabled());
  });

  it("reenables setup after its job fails while access is still missing", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: false, chromium_ready: true, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockRejectedValue(new Error("setup failed") as never);

    render(<LucidaScreen />);

    const prepare = await screen.findByRole("button", { name: "Подготовить доступ" });
    await user.click(prepare);
    await waitFor(() => expect(prepare).toBeEnabled());
  });

  it("disables setup and search with an installation explanation when Lucida is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: false, access_ready: false, chromium_ready: false, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);

    expect(await screen.findByText("Lucida недоступна в этой установке.")).toBeInTheDocument();
    expect(screen.getByText("Установите зависимости Lucida, чтобы использовать этот источник.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подготовить доступ" })).toBeDisabled();
    expect(screen.getByLabelText("Запрос Lucida")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Поиск" })).toBeDisabled();
  });

  it("disables setup and search until Chromium is installed", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: false, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);

    expect(await screen.findByText("Для Lucida требуется Chromium." )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подготовить доступ" })).toBeDisabled();
    expect(screen.getByLabelText("Запрос Lucida")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Поиск" })).toBeDisabled();
  });

  it("fails closed on a status error and refreshes before enabling search", async () => {
    const user = userEvent.setup();
    let statusAttempts = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) {
        statusAttempts += 1;
        return statusAttempts === 1
          ? jsonResponse({ detail: { code: "api.errors.lucida_failed", message: "Lucida status failed." } }, 502)
          : jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      }
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);

    expect(await screen.findByRole("status")).toHaveTextContent("Запрос к Lucida не выполнен.");
    expect(screen.getByRole("button", { name: "Подготовить доступ" })).toBeDisabled();
    expect(screen.getByLabelText("Запрос Lucida")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Поиск" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Обновить статус" }));

    await waitFor(() => expect(screen.getByLabelText("Запрос Lucida")).toBeEnabled());
    expect(statusAttempts).toBe(2);
  });

  it("treats an unknown status response as an error until an explicit refresh confirms readiness", async () => {
    const user = userEvent.setup();
    let statusAttempts = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) {
        statusAttempts += 1;
        return statusAttempts === 1
          ? jsonResponse({})
          : jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      }
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);

    expect(await screen.findByRole("status")).toHaveTextContent("Запрос к Lucida не выполнен.");
    expect(screen.getByRole("button", { name: "Подготовить доступ" })).toBeDisabled();
    expect(screen.getByLabelText("Запрос Lucida")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Обновить статус" }));

    await waitFor(() => expect(screen.getByLabelText("Запрос Lucida")).toBeEnabled());
  });

  it("renders a structured Lucida search failure", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ detail: { code: "api.errors.lucida_failed", message: "Lucida search failed." } }, 502);
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));

    expect(await screen.findByText("Запрос к Lucida не выполнен.")).toBeInTheDocument();
  });

  it("surfaces a setup job failure as a structured toast", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: false, chromium_ready: true, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockRejectedValue(new ApiError({ code: "api.errors.lucida_failed", message: "Lucida request failed." }) as never);

    render(<LucidaScreen />);
    await user.click(await screen.findByRole("button", { name: "Подготовить доступ" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith(
      { code: "api.errors.lucida_failed", message: "Lucida request failed." }, "error",
    ));
  });

  it("surfaces a download job failure as a structured toast", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/track", title: "Broken track" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockRejectedValue(new ApiError({ code: "api.errors.lucida_failed", message: "Lucida request failed." }) as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Broken track" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith(
      { code: "api.errors.lucida_failed", message: "Lucida request failed." }, "error",
    ));
  });

  it("reports a sanitized top-level download failure instead of completion", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/track", title: "Failed result" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockResolvedValue({
      items: [],
      error: { code: "api.errors.lucida_failed", message: "upstream diagnostic must not be shown" },
    } as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Failed result" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith({ code: "lucida.download_failed" }, "error"));
    expect(toast).not.toHaveBeenCalledWith({ code: "lucida.download_complete" });
  });

  it("reports a sanitized item failure as a partial download outcome", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/album", title: "Partial result" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockResolvedValue({
      items: [
        { status: "ok", title: "Downloaded item" },
        { status: "fail", error: { code: "api.errors.lucida_failed", message: "upstream diagnostic must not be shown" } },
      ],
    } as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Partial result" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith({ code: "lucida.download_partial" }, "warn"));
    expect(toast).not.toHaveBeenCalledWith({ code: "lucida.download_complete" });
  });

  it.each(["error", "message"] as const)("does not classify an item %s descriptor without status as completion", async (failureField) => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/track", title: "Missing status" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockResolvedValue({
      items: [{
        title: "Missing status",
        [failureField]: { code: "api.errors.lucida_failed", message: "upstream diagnostic must not be shown" },
      }],
    } as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Missing status" }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith({ code: "lucida.download_partial" }, "warn"));
    expect(toast).not.toHaveBeenCalledWith({ code: "lucida.download_complete" });
    expect(toast).not.toHaveBeenCalledWith(expect.objectContaining({ message: "upstream diagnostic must not be shown" }), expect.anything());
  });

  it("searches the selected service, lists albums before tracks, and downloads an item as a job", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) {
        expect(url).toContain("q=ambient");
        expect(url).toContain("service=qobuz");
        return jsonResponse({
          albums: [{ url: "https://lucida.example/album", title: "Album result", artist: "Album artist" }],
          tracks: [{ url: "https://lucida.example/track", title: "Track result", artist: "Track artist", album: "Track album" }],
        });
      }
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockResolvedValue({
      items: [{ status: "ok", title: "Album result" }, { status: "skip", title: "Existing item" }],
    } as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));

    const albums = await screen.findByRole("heading", { name: "Альбомы" });
    const tracks = screen.getByRole("heading", { name: "Треки" });
    expect(albums.compareDocumentPosition(tracks) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Скачать: Album result" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledWith(
      "/api/lucida/download",
      { url: "https://lucida.example/album", kind: "album", service: "qobuz" },
      expect.anything(),
    ));
    expect(toast).toHaveBeenCalledWith({ code: "lucida.download_complete" });
  });

  it("starts only one download job for a result while that result is pending", async () => {
    const user = userEvent.setup();
    const download = deferred<{ items: unknown[] }>();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/track", title: "Pending track" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockReturnValue(download.promise as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    const downloadButton = await screen.findByRole("button", { name: "Скачать: Pending track" });
    await user.click(downloadButton);
    expect(downloadButton).toBeDisabled();
    await user.click(downloadButton);

    expect(startJob).toHaveBeenCalledTimes(1);
    await act(async () => {
      download.resolve({ items: [] });
      await download.promise;
    });
    await waitFor(() => expect(downloadButton).toBeEnabled());
  });

  it("omits malformed search entries that have no nonempty URL", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{}], tracks: [] });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));

    expect(await screen.findByText("Ничего не найдено")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Скачать:/ })).not.toBeInTheDocument();
  });

  it("ignores a pending result from the previous service and downloads with the result service", async () => {
    const user = userEvent.setup();
    const settings = deferred<ReturnType<typeof jsonResponse>>();
    const qobuzSearch = deferred<ReturnType<typeof jsonResponse>>();
    let qobuzSearchInit: RequestInit | undefined;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/settings") return settings.promise;
      if (url.startsWith("/api/lucida/status")) return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" }));
      if (url.includes("/api/lucida/search") && url.includes("service=qobuz")) {
        qobuzSearchInit = init;
        return qobuzSearch.promise;
      }
      if (url.includes("/api/lucida/search") && url.includes("service=amazon")) {
        return Promise.resolve(jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/amazon-track", title: "Amazon result" }] }));
      }
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockResolvedValue({ items: [{ status: "ok", title: "Amazon result" }] } as never);

    render(<LucidaScreen />);
    await act(async () => {
      settings.resolve(jsonResponse({ lucida_service: "qobuz" }));
      await settings.promise;
    });
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(screen.getByRole("button", { name: "Amazon Music" }));

    expect(qobuzSearchInit?.signal?.aborted).toBe(true);
    expect(screen.queryByText("Qobuz result")).not.toBeInTheDocument();
    await act(async () => {
      qobuzSearch.resolve(jsonResponse({ albums: [{ url: "https://lucida.example/qobuz-album", title: "Qobuz result" }], tracks: [] }));
      await qobuzSearch.promise;
    });
    expect(screen.queryByText("Qobuz result")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Amazon result" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledWith(
      "/api/lucida/download",
      { url: "https://lucida.example/amazon-track", kind: "track", service: "amazon" },
      expect.anything(),
    ));
  });

  it("ignores a pending status response from the previous service", async () => {
    const user = userEvent.setup();
    const qobuzStatus = deferred<ReturnType<typeof jsonResponse>>();
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/settings") return Promise.resolve(jsonResponse({ lucida_service: "qobuz" }));
      if (url.includes("/api/lucida/status") && url.includes("service=qobuz")) return qobuzStatus.promise;
      if (url.includes("/api/lucida/status") && url.includes("service=amazon")) {
        return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "amazon" }));
      }
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);

    await user.click(screen.getByRole("button", { name: "Amazon Music" }));
    const query = await screen.findByLabelText("Запрос Lucida");
    await waitFor(() => expect(query).toBeEnabled());

    await act(async () => {
      qobuzStatus.resolve(jsonResponse({ available: false, access_ready: false, chromium_ready: false, service: "qobuz" }));
      await qobuzStatus.promise;
    });

    expect(query).toBeEnabled();
  });

  it("keeps a manually selected Amazon service when deferred settings resolve to Qobuz", async () => {
    const user = userEvent.setup();
    const settings = deferred<ReturnType<typeof jsonResponse>>();
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/settings") return settings.promise;
      if (url.includes("/api/lucida/status") && url.includes("service=qobuz")) {
        return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" }));
      }
      if (url.includes("/api/lucida/status") && url.includes("service=amazon")) {
        return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "amazon" }));
      }
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.click(screen.getByRole("button", { name: "Amazon Music" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Amazon Music" })).toHaveAttribute("aria-pressed", "true"));

    await act(async () => {
      settings.resolve(jsonResponse({ lucida_service: "qobuz" }));
      await settings.promise;
    });

    expect(screen.getByRole("button", { name: "Amazon Music" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Запрос Lucida")).toBeEnabled();
  });

  it("abandons a pending settings request when the screen unmounts", async () => {
    const settings = deferred<ReturnType<typeof jsonResponse>>();
    let settingsInit: RequestInit | undefined;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/settings") {
        settingsInit = init;
        return settings.promise;
      }
      if (url.startsWith("/api/lucida/status")) {
        return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" }));
      }
      throw new Error(`unexpected ${url}`);
    }));

    const view = render(<LucidaScreen />);
    view.unmount();

    expect(settingsInit?.signal?.aborted).toBe(true);
    await act(async () => {
      settings.resolve(jsonResponse({ lucida_service: "amazon" }));
      await settings.promise;
    });
  });

  it("abandons a pending status request when the screen unmounts", async () => {
    const status = deferred<ReturnType<typeof jsonResponse>>();
    let statusInit: RequestInit | undefined;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/settings") return Promise.resolve(jsonResponse({ lucida_service: "qobuz" }));
      if (url.startsWith("/api/lucida/status")) {
        statusInit = init;
        return status.promise;
      }
      throw new Error(`unexpected ${url}`);
    }));

    const view = render(<LucidaScreen />);
    await waitFor(() => expect(statusInit).toBeDefined());
    view.unmount();

    expect(statusInit?.signal?.aborted).toBe(true);
    await act(async () => {
      status.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" }));
      await status.promise;
    });
  });

  it("aborts a pending search without rendering an error after the screen unmounts", async () => {
    const user = userEvent.setup();
    const search = deferred<ReturnType<typeof jsonResponse>>();
    let searchInit: RequestInit | undefined;
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/settings") return Promise.resolve(jsonResponse({ lucida_service: "qobuz" }));
      if (url.startsWith("/api/lucida/status")) return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" }));
      if (url.startsWith("/api/lucida/search")) {
        searchInit = init;
        return search.promise;
      }
      throw new Error(`unexpected ${url}`);
    }));

    const view = render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await waitFor(() => expect(searchInit).toBeDefined());
    view.unmount();

    expect(searchInit?.signal?.aborted).toBe(true);
    await act(async () => {
      search.resolve(jsonResponse({ albums: [], tracks: [] }));
      await search.promise;
    });
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("does not refresh status when setup completes after the screen unmounts", async () => {
    const user = userEvent.setup();
    const setup = deferred<{ access_ready: boolean }>();
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: false, chromium_ready: true, service: "qobuz" });
      throw new Error(`unexpected ${url}`);
    });
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", fetchMock);
    vi.mocked(startJob).mockReturnValue(setup.promise as never);

    const view = render(<LucidaScreen />);
    await user.click(await screen.findByRole("button", { name: "Подготовить доступ" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledTimes(1));
    const statusCallsBeforeUnmount = fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/lucida/status")).length;
    view.unmount();

    await act(async () => {
      setup.resolve({ access_ready: true });
      await setup.promise;
    });
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/lucida/status"))).toHaveLength(statusCallsBeforeUnmount);
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("does not update progress or toast when a download finishes after the screen unmounts", async () => {
    const user = userEvent.setup();
    const download = deferred<{ items: unknown[] }>();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/track", title: "Deferred track" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockReturnValue(download.promise as never);

    const view = render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Deferred track" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledTimes(1));
    const options = vi.mocked(startJob).mock.calls[0][2];

    view.unmount();
    await act(async () => {
      options?.onProgress?.({ percent: 50, msg: "still downloading" });
      download.resolve({ items: [] });
      await download.promise;
    });

    expect(toast).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("does not show a download error when the deferred job rejects after unmount", async () => {
    const user = userEvent.setup();
    const download = deferred<{ items: unknown[] }>();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [], tracks: [{ url: "https://lucida.example/error-track", title: "Error track" }] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockReturnValue(download.promise as never);

    const view = render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Error track" }));
    await waitFor(() => expect(startJob).toHaveBeenCalledTimes(1));
    view.unmount();
    await act(async () => {
      download.reject(new Error("download failed"));
      await Promise.resolve();
    });

    expect(toast).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("renders result covers and keeps album download as the only album action", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({
        albums: [{ url: "https://lucida.example/album", title: "Covered album", artist: "Album artist", cover_url: "https://images.example/album.jpg" }],
        tracks: [{ url: "https://lucida.example/track", title: "Covered track", artist: "Track artist", cover_url: "https://images.example/track.jpg" }],
      });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));

    expect(await screen.findByAltText("Обложка: Covered album")).toHaveAttribute("src", "https://images.example/album.jpg");
    expect(screen.getByAltText("Обложка: Covered track")).toHaveAttribute("src", "https://images.example/track.jpg");
    expect(screen.getByRole("button", { name: "Скачать: Covered album" })).toBeInTheDocument();
    expect(screen.queryByText("альбом")).not.toBeInTheDocument();
    expect(screen.queryByText("трек")).not.toBeInTheDocument();
    const disclosure = screen.getByRole("button", { name: "Показать треклист: Covered album" });
    expect(disclosure).toHaveAttribute("aria-expanded", "false");
    expect(disclosure).toHaveClass("lucida-disclosure");
    expect(disclosure.closest(".t-actions")).toBeInTheDocument();
    expect(disclosure.compareDocumentPosition(screen.getByRole("button", { name: "Скачать: Covered album" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(disclosure.querySelector("span[aria-hidden='true']")).toBeInTheDocument();
  });

  it("renders album results in a dedicated two-column grid", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({
        albums: [
          { url: "https://lucida.example/a1", title: "Album one" },
          { url: "https://lucida.example/a2", title: "Album two" },
          { url: "https://lucida.example/a3", title: "Album three" },
        ],
        tracks: [],
      });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));

    const grid = await screen.findByTestId("lucida-albums-grid");
    expect(grid).toHaveClass("lucida-albums-grid", "lucida-results-grid");
    expect(grid.querySelectorAll(".lucida-result-card")).toHaveLength(3);
  });

  it("renders albums and tracks in separate two-column grids", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({
        albums: [{ url: "https://lucida.example/a1", title: "Album one" }],
        tracks: [{ url: "https://lucida.example/t1", title: "Track one" }, { url: "https://lucida.example/t2", title: "Track two" }],
      });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));

    const grids = await screen.findAllByTestId(/lucida-(albums|tracks)-grid/);
    expect(grids).toHaveLength(2);
    expect(grids.map((grid) => grid).every((grid) => grid.classList.contains("lucida-results-grid"))).toBe(true);
    expect(grids[0].querySelectorAll(".lucida-result-card")).toHaveLength(1);
    expect(grids[1].querySelectorAll(".lucida-result-card")).toHaveLength(2);
  });

  it("loads an album tracklist inline without nested covers or download buttons", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{ url: "https://lucida.example/album", title: "Expanded album" }], tracks: [] });
      if (url.startsWith("/api/lucida/release")) return jsonResponse({ title: "Expanded album", artist: "Album artist", tracks: [{ number: 1, title: "Nested track", duration: 190 }], track_count: 1 });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Показать треклист: Expanded album" }));

    const tracklist = await screen.findByRole("region", { name: "Треклист: Expanded album" });
    expect(tracklist).toHaveTextContent("1");
    expect(tracklist).toHaveTextContent("Nested track");
    expect(tracklist).toHaveTextContent("3:10");
    const disclosure = screen.getByRole("button", { name: "Скрыть треклист: Expanded album" });
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    expect(disclosure).toHaveClass("lucida-disclosure", "is-expanded");
    expect(disclosure.closest(".t-actions")).toBeInTheDocument();
    expect(screen.queryByAltText("Обложка: Nested track")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Скачать: Nested track" })).not.toBeInTheDocument();
  });

  it("requests an Amazon release preview with the service that produced the result", async () => {
    const user = userEvent.setup();
    let releaseUrl = "";
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "amazon" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{ url: "https://lucida.example/amazon-album", title: "Amazon album" }], tracks: [] });
      if (url.startsWith("/api/lucida/release")) {
        releaseUrl = url;
        return jsonResponse({ title: "Amazon album", artist: "Artist", tracks: [], track_count: 0 });
      }
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.click(screen.getByRole("button", { name: "Amazon Music" }));
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Показать треклист: Amazon album" }));

    expect(await screen.findByRole("region", { name: "Треклист: Amazon album" })).toBeInTheDocument();
    expect(releaseUrl).toContain("service=amazon");
  });

  it("shows a loading state while an expanded album tracklist is requested", async () => {
    const user = userEvent.setup();
    const release = deferred<ReturnType<typeof jsonResponse>>();
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/settings") return Promise.resolve(jsonResponse({ lucida_service: "qobuz" }));
      if (url.startsWith("/api/lucida/status")) return Promise.resolve(jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" }));
      if (url.startsWith("/api/lucida/search")) return Promise.resolve(jsonResponse({ albums: [{ url: "https://lucida.example/loading-album", title: "Loading album" }], tracks: [] }));
      if (url.startsWith("/api/lucida/release")) return release.promise;
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Показать треклист: Loading album" }));

    expect(await screen.findByRole("region", { name: "Треклист: Loading album" })).toHaveTextContent("Загружаем треклист…");

    await act(async () => {
      release.resolve(jsonResponse({ title: "Loading album", artist: "Artist", tracks: [], track_count: 0 }));
      await release.promise;
    });
  });

  it("explains a failed tracklist preview and retries it from the expanded album", async () => {
    const user = userEvent.setup();
    let releaseAttempts = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{ url: "https://lucida.example/retry-album", title: "Retry album" }], tracks: [] });
      if (url.startsWith("/api/lucida/release")) {
        releaseAttempts += 1;
        return releaseAttempts === 1
          ? jsonResponse({ detail: "upstream unavailable" }, 502)
          : jsonResponse({ title: "Retry album", artist: "Artist", tracks: [{ number: 1, title: "Recovered track" }], track_count: 1 });
      }
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Показать треклист: Retry album" }));

    const tracklist = await screen.findByRole("region", { name: "Треклист: Retry album" });
    expect(tracklist).toHaveTextContent("Не удалось загрузить этот треклист.");
    await user.click(screen.getByRole("button", { name: "Повторить треклист: Retry album" }));

    expect(await screen.findByText("Recovered track")).toBeInTheDocument();
    expect(releaseAttempts).toBe(2);
  });

  it("shows the empty tracklist state for a valid release with no tracks", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{ url: "https://lucida.example/empty-album", title: "Empty album" }], tracks: [] });
      if (url.startsWith("/api/lucida/release")) return jsonResponse({ title: "Empty album", artist: "Artist", tracks: [], track_count: 0 });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Показать треклист: Empty album" }));

    expect(await screen.findByRole("region", { name: "Треклист: Empty album" })).toHaveTextContent("В этом альбоме нет треков.");
  });

  it("degrades malformed tracklist payloads by rendering only valid tracks", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{ url: "https://lucida.example/malformed-album", title: "Malformed album" }], tracks: [] });
      if (url.startsWith("/api/lucida/release")) return jsonResponse({
        title: "Malformed album",
        artist: "Artist",
        tracks: [{ number: 1, title: "Valid track", duration: "2:30" }, { number: "2", title: "Invalid number" }, { number: 3 }, null],
        track_count: "not a number",
      });
      throw new Error(`unexpected ${url}`);
    }));

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Показать треклист: Malformed album" }));

    const tracklist = await screen.findByRole("region", { name: "Треклист: Malformed album" });
    expect(tracklist).toHaveTextContent("1");
    expect(tracklist).toHaveTextContent("Valid track");
    expect(tracklist).toHaveTextContent("2:30");
    expect(tracklist).not.toHaveTextContent("Invalid number");
  });

  it("shows completed tracks and percent from flat Lucida job progress", async () => {
    const user = userEvent.setup();
    const download = deferred<{ items: unknown[] }>();
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/settings") return jsonResponse({ lucida_service: "qobuz" });
      if (url.startsWith("/api/lucida/status")) return jsonResponse({ available: true, access_ready: true, chromium_ready: true, service: "qobuz" });
      if (url.startsWith("/api/lucida/search")) return jsonResponse({ albums: [{ url: "https://lucida.example/album", title: "Progress album" }], tracks: [] });
      throw new Error(`unexpected ${url}`);
    }));
    vi.mocked(startJob).mockReturnValue(download.promise as never);

    render(<LucidaScreen />);
    await user.type(await screen.findByLabelText("Запрос Lucida"), "ambient");
    await user.click(screen.getByRole("button", { name: "Поиск" }));
    await user.click(await screen.findByRole("button", { name: "Скачать: Progress album" }));

    const options = vi.mocked(startJob).mock.calls[0][2];
    await act(async () => {
      options?.onProgress?.({ done: 2, total: 5, percent: 40 } as never);
    });

    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText("Скачано треков: 2/5 · 40%")).toBeInTheDocument();
    await act(async () => {
      download.resolve({ items: [] });
      await download.promise;
    });
  });

});
