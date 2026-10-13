import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import SettingsScreen from "../src/views/SettingsScreen";
import { toast } from "../src/lib/toast";
import { changeLanguage } from "../src/i18n";
import * as jobs from "../src/lib/jobs";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const SETTINGS = {
  output_dir: "/Music/lib",
  default_format: "mp3",
  default_quality: 192,
  source_format: "opus",
  source_formats: ["m4a", "opus"],
  shazam_file: "/shazam.txt",
  primuse_sidecar: false,
  youtube_browser: "safari",
  youtube_browsers: ["safari", "chrome"],
  youtube_cookies_file: "",
  youtube_cookies_set: false,
  ytmusic_no_clips: true,
  ytm_feedback_action: "like",
  search_source: "youtube_music",
  name_translit: "auto",
  metadata_sources: ["itunes", "deezer"],
  metadata_sources_order: ["itunes", "deezer", "discogs"],
  metadata_sources_available: ["itunes", "deezer", "discogs"],
  formats: ["mp3", "m4a", "opus", "flac"],
  language: "ru" as const,
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.mocked(toast).mockClear();
  fetchMock = vi.fn(async (url: string) => {
    if (url === "/api/settings") return jsonResponse(SETTINGS);
    if (url === "/api/ytmusic/status") return jsonResponse({ connected: false });
    if (url === "/api/ytmusic/auth/browsers") return jsonResponse({ browsers: [{ name: "chrome", profiles: ["Default"] }] });
    throw new Error(`unexpected ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((settle, fail) => {
    resolve = settle;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function renderScreen() {
  return render(
    <DialogProvider>
      <SettingsScreen />
    </DialogProvider>,
  );
}

describe("SettingsScreen", () => {
  it("карточки и исходные значения", async () => {
    renderScreen();
    expect(await screen.findByText("Библиотека")).toBeInTheDocument();
    expect(screen.getByText("Источники")).toBeInTheDocument();
    expect(screen.getByText("Файлы")).toBeInTheDocument();
    expect(screen.getByText("Primuse")).toBeInTheDocument();
    // Порядок источников из настроек.
    expect(screen.getByText("discogs")).toBeInTheDocument();
    // Кнопка «Сохранить» недоступна без изменений.
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeDisabled();
  });

  it("свитчер Primuse и сохранение — PUT /api/settings с новым значением", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Primuse");
    await user.click(screen.getByText("Сохранять .lrc и -cover.jpg"));
    // Кнопка активируется (dirty).
    await waitFor(() => expect(screen.getByRole("button", { name: "Сохранить" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Настройки сохранены"));
    const call = fetchMock.mock.calls.find(([u, init]) => u === "/api/settings" && (init as RequestInit | undefined)?.method === "PUT");
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      primuse_sidecar: true,
      name_translit: "auto",
      metadata_sources: ["itunes", "deezer"],
      metadata_sources_order: ["itunes", "deezer", "discogs"],
      ytmusic_no_clips: true,
    });
  });

  it("сегмент «Язык имён» и «Принимать рекомендации как» уходят в payload", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Язык имён");
    await user.click(screen.getByRole("button", { name: "Латиница" }));
    await user.click(screen.getByRole("button", { name: "В библиотеку" }));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() =>
      expect(JSON.parse(String(fetchMock.mock.calls.find(([u, init]) => u === "/api/settings" && (init as RequestInit | undefined)?.method === "PUT")?.[1]?.body))).toMatchObject({
        name_translit: "latin",
        ytm_feedback_action: "library",
      }),
    );
  });

  it("переключает язык сразу и сохраняет отдельной настройкой", async () => {
    const user = userEvent.setup();
    renderScreen();

    await screen.findByRole("combobox", { name: "Язык" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Язык" }), "en");

    expect(screen.getByRole("combobox", { name: "Language" })).toHaveValue("en");
    await waitFor(() =>
      expect(JSON.parse(String(fetchMock.mock.calls.find(([url, init]) => url === "/api/settings" && (init as RequestInit | undefined)?.method === "PUT")?.[1]?.body))).toEqual({ language: "en" }),
    );
  });

  it("после отклонённого deferred RU PUT сохраняет итоговый EN", async () => {
    const user = userEvent.setup();
    const ruSave = deferred<ReturnType<typeof jsonResponse>>();
    const enSave = deferred<ReturnType<typeof jsonResponse>>();
    const languagePayloads: unknown[] = [];
    let persistedLanguage: "ru" | "en" = "ru";
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === "/api/settings" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body));
        languagePayloads.push(payload);
        if (payload.language === "ru") return ruSave.promise.then((response) => {
          persistedLanguage = "ru";
          return response;
        });
        if (payload.language === "en") return enSave.promise.then((response) => {
          persistedLanguage = "en";
          return response;
        });
      }
      if (url === "/api/settings") return jsonResponse(SETTINGS);
      if (url === "/api/ytmusic/status") return jsonResponse({ connected: false });
      if (url === "/api/ytmusic/auth/browsers") return jsonResponse({ browsers: [{ name: "chrome", profiles: ["Default"] }] });
      throw new Error(`unexpected ${url}`);
    });
    renderScreen();

    const language = await screen.findByRole("combobox", { name: "Язык" });
    await user.selectOptions(language, "ru");
    await user.selectOptions(language, "en");

    expect(languagePayloads).toEqual([{ language: "ru" }]);
    expect(screen.getByRole("combobox", { name: "Language" })).toHaveValue("en");

    await act(async () => {
      ruSave.reject(new Error("rejected RU save"));
    });
    await waitFor(() => expect(languagePayloads).toEqual([{ language: "ru" }, { language: "en" }]));

    await act(async () => {
      enSave.resolve(jsonResponse({}));
    });
    await waitFor(() => expect(persistedLanguage).toBe("en"));
    expect(screen.getByRole("combobox", { name: "Language" })).toHaveValue("en");
  });

  it("смена локали перерисовывает загруженную форму без изменения значений", async () => {
    await changeLanguage("ru");
    renderScreen();
    const directory = await screen.findByDisplayValue("/Music/lib");
    await act(async () => { await changeLanguage("en"); });

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(directory).toHaveValue("/Music/lib");
    expect(screen.getByText("discogs")).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("перерисовывает авторизацию YouTube Music при смене локали, сохраняя данные браузера", async () => {
    await changeLanguage("ru");
    renderScreen();
    expect(await screen.findByRole("button", { name: "Найти аккаунты" })).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });

    expect(screen.getByText("Browser cookies")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Find accounts" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Browser" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check sign-in" })).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("переводит завершённый deferred поиск аккаунтов, не меняя provider data", async () => {
    const user = userEvent.setup();
    const accounts = deferred<{ candidates: { authuser: number; likes: number; page_id: string; account: { name: string; handle: string } }[] }>();
    vi.spyOn(jobs, "startJob").mockImplementation((_endpoint, _body, options) => {
      options?.onProgress?.({ percent: 50, message: { code: "jobs.auth.read_cookies" } });
      return accounts.promise;
    });
    renderScreen();
    const browser = await screen.findByRole("combobox", { name: "Браузер" });
    await waitFor(() => expect(browser).toBeEnabled());
    await user.selectOptions(browser, "chrome");
    await user.click(screen.getByRole("button", { name: "Найти аккаунты" }));
    expect(screen.getByText("Читаю куки браузера…")).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });
    expect(screen.getByText("Reading browser cookies…")).toBeInTheDocument();

    await act(async () => {
      accounts.resolve({ candidates: [{ authuser: 2, likes: 12, page_id: "brand-page", account: { name: "Provider Account", handle: "@provider" } }] });
    });
    await screen.findByText("Accounts found: 1");
    expect(screen.getByRole("option", { name: /Provider Account \(@provider\) \(brand\) — 12 likes, authuser 2/ })).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("переводит deferred browser-extract fallback для аккаунта без имени", async () => {
    const user = userEvent.setup();
    const extraction = deferred<{ authuser: number; account?: { name?: string } }>();
    vi.spyOn(jobs, "startJob").mockImplementation((_endpoint, _body, options) => {
      options?.onProgress?.({ percent: 50, message: { code: "jobs.auth.read_cookies" } });
      return extraction.promise;
    });
    renderScreen();
    const browser = await screen.findByRole("combobox", { name: "Браузер" });
    await waitFor(() => expect(browser).toBeEnabled());
    await user.selectOptions(browser, "chrome");
    await user.click(screen.getByRole("button", { name: "Извлечь из браузера" }));
    expect(screen.getByText("Читаю куки браузера…")).toBeInTheDocument();

    await act(async () => {
      extraction.resolve({ authuser: 2 });
    });
    expect(await screen.findByText(/неизвестный аккаунт/)).toBeInTheDocument();

    await act(async () => { await changeLanguage("en"); });
    expect(screen.getByText(/unknown account/)).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("переводит завершённые deferred проверки входа и 18+, сохраняя browser/title", async () => {
    const user = userEvent.setup();
    const login = deferred<unknown>();
    const age = deferred<unknown>();
    fetchMock.mockImplementation(async (url: string) => {
      if (url === "/api/settings") return jsonResponse(SETTINGS);
      if (url === "/api/ytmusic/status") return jsonResponse({ connected: false });
      if (url === "/api/ytmusic/auth/browsers") return jsonResponse({ browsers: [{ name: "chrome", profiles: ["Default"] }] });
      if (url === "/api/settings/cookies/check") return jsonResponse(await login.promise);
      if (url === "/api/settings/cookies/verify-age") return jsonResponse(await age.promise);
      throw new Error(`unexpected ${url}`);
    });
    renderScreen();
    await screen.findByRole("button", { name: "Проверить вход" });
    await user.click(screen.getByRole("button", { name: "Проверить вход" }));
    await act(async () => {
      login.resolve({ browser: "chrome", browsers: [{ browser: "chrome", auth: true, cookies: 4 }] });
    });
    await screen.findByText("Вход есть (chrome) — можно качать");

    await user.click(screen.getByRole("button", { name: "Проверить 18+" }));
    await act(async () => {
      age.resolve({ verified_18: true, checks: [{ source: "YouTube", ok: true, title: "Provider title" }] });
    });
    await screen.findByText("Provider title");

    await act(async () => { await changeLanguage("en"); });
    expect(screen.getByText("Signed in (chrome) — downloads are available")).toBeInTheDocument();
    expect(screen.getByText("18+:" )).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText("Provider title")).toBeInTheDocument();
    await changeLanguage("ru");
  });

  it("сохраняет новый язык при ошибке PUT и показывает локализованное уведомление", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === "/api/settings" && init?.method === "PUT") return jsonResponse({ detail: "no" }, 500);
      if (url === "/api/settings") return jsonResponse(SETTINGS);
      if (url === "/api/ytmusic/status") return jsonResponse({ connected: false });
      if (url === "/api/ytmusic/auth/browsers") return jsonResponse({ browsers: [] });
      throw new Error(`unexpected ${url}`);
    });
    renderScreen();

    await user.selectOptions(await screen.findByRole("combobox", { name: "Язык" }), "en");

    expect(screen.getByRole("combobox", { name: "Language" })).toHaveValue("en");
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Language changed, but could not be saved", "error"));
  });

  it("свитчер no_clips и источник поиска", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByRole("heading", { name: "YouTube Music" });
    await user.click(screen.getByText("Избегать клипов: качать аудиоверсии (Topic) вместо клипов"));
    await user.click(screen.getByRole("button", { name: "YouTube" }));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() =>
      expect(JSON.parse(String(fetchMock.mock.calls.find(([u, init]) => u === "/api/settings" && (init as RequestInit | undefined)?.method === "PUT")?.[1]?.body))).toMatchObject({
        ytmusic_no_clips: false,
        search_source: "youtube",
      }),
    );
  });

  /* Чтение настроек (в т.ч. скан профилей браузеров) — не мгновенное:
   вместо полностью пустого экрана — скелетон той же сетки карточек. */
  it("пока настройки грузятся — скелетон сетки карточек, а не пустой экран", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    renderScreen();

    const grid = document.querySelector(".set-grid");
    expect(grid).toBeTruthy();
    const cols = grid!.querySelectorAll(".set-col");
    expect(cols.length).toBe(2);
    const cards = grid!.querySelectorAll(".panel");
    expect(cards.length).toBeGreaterThanOrEqual(4);
    cards.forEach((c) => expect(c.querySelector(".skeleton")).toBeTruthy());
    // Формы ещё нет — «Сохранить» не рендерится до загрузки.
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
  });

});
