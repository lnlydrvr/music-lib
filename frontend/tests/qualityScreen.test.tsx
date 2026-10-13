import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import QualityScreen, { categoryLabel } from "../src/views/QualityScreen";
import { trackEditorDialog, trackBatchEditorDialog } from "../src/features/editor";
import { toast } from "../src/lib/toast";
import { changeLanguage } from "../src/i18n";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));
vi.mock("../src/features/editor", () => ({
  trackEditorDialog: vi.fn(async () => null),
  trackBatchEditorDialog: vi.fn(async () => null),
}));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const REPORT = {
  total: 5,
  issues: [
    { category: "missing", message: { code: "diagnostics.health.missing_tag", params: { field: "year" }, message: "Missing tag “Year”" } },
    { category: "whitespace", message: { code: "diagnostics.lint.whitespace", params: { field: "title", value: "Song" }, message: "“Title”: extra spaces in “Song”" } },
  ],
  changes: [{ path: "/lib/b.mp3", field: "genre", old: "Rock ", new: "Rock" }],
  tracks: [
    {
      path: "/lib/a.mp3",
      title: "Alpha",
      artist: "Artist A",
      album: "Album A",
      issues: [{ category: "missing", message: { code: "diagnostics.health.missing_tag", params: { field: "year" }, message: "Missing tag “Year”" } }],
      changes: [],
    },
    {
      path: "/lib/b.mp3",
      title: "Beta",
      artist: "Artist B",
      album: "",
      issues: [{ category: "whitespace", message: { code: "diagnostics.lint.whitespace", params: { field: "title", value: "Song" }, message: "“Title”: extra spaces in “Song”" }, auto_fixable: true }],
      changes: [{ path: "/lib/b.mp3", field: "genre", old: "Rock ", new: "Rock" }],
    },
  ],
};

const PLAN = {
  counts: { changes: 1, fixes: 1 },
  changes: [{ path: "/lib/b.mp3", field: "genre", old: "Rock ", new: "Rock" }],
  fixes: [{ action: "move", from: "/lib/loose.mp3", to: "/lib/Artist/Album/loose.mp3" }],
  conflicts: [{ path: "/lib/dupe.mp3", kind: "target_exists", message: { code: "diagnostics.quality.target_occupied", params: {}, message: "Target path occupied" } }],
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.mocked(toast).mockClear();
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith("/api/library/quality/plan")) return jsonResponse(PLAN);
    if (url.startsWith("/api/library/quality/apply")) return jsonResponse({ applied: 2, skipped: 0, conflicts: 1, errors: 0 });
    if (url.startsWith("/api/library/quality")) return jsonResponse(REPORT);
    throw new Error(`unexpected ${url} ${init?.body ?? ""}`);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.classList.remove("sel-open");
});

function renderScreen() {
  return render(
    <DialogProvider>
      <QualityScreen />
    </DialogProvider>,
  );
}

describe("QualityScreen", () => {
  it("переводит известные category/cause ID и безопасно оставляет неизвестный ID", async () => {
    expect(categoryLabel("missing")).toBe("Незаполненные теги");
    expect(categoryLabel("disc_number")).toBe("Номера дисков");
    expect(categoryLabel("future_backend_id")).toBe("future_backend_id");

    await act(async () => { await changeLanguage("en"); });
    expect(categoryLabel("disc_number")).toBe("Disc numbers");
  });

  it("чипы, пиллы-фильтры и плоский список", async () => {
    renderScreen();
    expect(await screen.findByText("Проблем: 2")).toBeInTheDocument();
    expect(screen.getByText("Авто-исправления: 1")).toBeInTheDocument();
    expect(screen.getByText("Проверено треков: 5")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скрыть категорию: Незаполненные теги" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скрыть категорию: Лишние пробелы" })).toBeInTheDocument();

    // Плоский список: обе карточки по одному разу, у Beta — автофикс и «Исправить».
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Нет тега «Год»")).toBeInTheDocument();
    expect(screen.getByTitle("Столько изменений предложит автоисправление")).toHaveTextContent("авто-исправления: 1");
    expect(screen.getByRole("button", { name: "Исправить" })).toBeInTheDocument();
    // У Alpha нет текста — кнопка «Текст».
    expect(screen.getAllByRole("button", { name: "Текст" })).toHaveLength(1);

    // Пилла скрывает категорию: Alpha исчезает.
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Скрыть категорию: Незаполненные теги" }));
    expect(await screen.findByRole("button", { name: "Показать категорию: Незаполненные теги" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Alpha")).not.toBeInTheDocument());
    expect(screen.getByText("Beta")).toBeInTheDocument();
    // «Показать все» возвращает.
    await user.click(screen.getByRole("button", { name: "Показать все" }));
    await waitFor(() => expect(screen.getByText("Alpha")).toBeInTheDocument());
  });

  it("выбор: чекбокс → selbar; «Выбрать все»; смена фильтра сбрасывает выбор", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Alpha");

    await user.click(screen.getByRole("checkbox", { name: "Выбрать: Alpha" }));
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "Действия с выбранными треками" }).className).toContain("show"));
    expect(screen.getByText("Выбрано: 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Выбрать все (2)" }));
    expect(screen.getByText("Выбрано: 2")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Снять выделение (2)" })).toBeInTheDocument());

    // Смена фильтра сбрасывает выбор (живёт в рамках показанного списка).
    await user.click(screen.getByRole("button", { name: "Скрыть категорию: Лишние пробелы" }));
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "Действия с выбранными треками" }).className).not.toContain("show"));
  });

  it("«Нормализовать»: план → confirmPlanDialog с diff и конфликтами → применение", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Alpha");
    await user.click(screen.getByRole("checkbox", { name: "Выбрать: Beta" }));

    await user.click(screen.getByRole("button", { name: "Нормализовать" }));
    // План запрослен с выбранным путём.
    await waitFor(() =>
      expect(JSON.parse(String(fetchMock.mock.calls.find(([u]) => u === "/api/library/quality/plan")?.[1]?.body))).toEqual({
        paths: ["/lib/b.mp3"],
      }),
    );

    // Диалог подтверждения: diff, переносы, конфликты.
    const dlg = await screen.findByRole("dialog");
    expect(within(dlg).getByText("Применить изменения?")).toBeInTheDocument();
    expect(within(dlg).getByText("Изменения тегов — 1")).toBeInTheDocument();
    expect(within(dlg).getByText("Файлы — 1")).toBeInTheDocument();
    expect(within(dlg).getByText("Конфликты — 1")).toBeInTheDocument();
    expect(within(dlg).getByText("эти элементы будут пропущены, остальное применится")).toBeInTheDocument();
    expect(within(dlg).getByText("Целевой путь занят")).toBeInTheDocument();
    expect(within(dlg).getByText("Перенос")).toBeInTheDocument();
    // Diff-подсветка: у старого значения выделен хвостовой пробел (.del).
    expect(dlg.querySelector("td .del")).toBeTruthy();

    await user.click(within(dlg).getByRole("button", { name: "Применить (2)" }));
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith("Применено: 2, пропущено: 0, конфликтов: 1", "warn"),
    );
    const applyCall = fetchMock.mock.calls.find(([u]) => u === "/api/library/quality/apply");
    expect(JSON.parse(String(applyCall?.[1]?.body))).toEqual({ paths: ["/lib/b.mp3"] });
  });

  it("открытый диалог плана меняет локаль для заголовка, тела и действий", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Alpha");
    await user.click(screen.getByRole("checkbox", { name: "Выбрать: Beta" }));
    await user.click(screen.getByRole("button", { name: "Нормализовать" }));
    const dialog = await screen.findByRole("dialog");
    const apply = within(dialog).getByRole("button", { name: "Применить (2)" });

    await act(async () => { await changeLanguage("en"); });

    expect(dialog).toHaveTextContent("Apply changes?");
    expect(dialog).toHaveTextContent("Tag changes — 1");
    expect(within(dialog).getByRole("button", { name: "Apply (2)" })).toBe(apply);
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("«Исправить» на карточке: план только для этого трека", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Beta");
    await user.click(screen.getByRole("button", { name: "Исправить" }));
    await screen.findByText("Применить изменения?");
    await waitFor(() =>
      expect(JSON.parse(String(fetchMock.mock.calls.find(([u]) => u === "/api/library/quality/plan")?.[1]?.body))).toEqual({
        paths: ["/lib/b.mp3"],
      }),
    );
    // Отмена — без применения.
    const user2 = userEvent.setup();
    await user2.click(screen.getByRole("button", { name: "Отмена" }));
    await waitFor(() => expect(screen.queryByText("Применить изменения?")).not.toBeInTheDocument());
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/library/quality/apply")).toBe(false);
  });

  it("массовое обновление текстов блокирует повторный запуск и показывает фазу обновления списка", async () => {
    let resolveRefresh: (() => void) | undefined;
    let qualityCalls = 0;
    let resolveLyrics: (() => void) | undefined;
    fetchMock.mockImplementation((url: string) => {
      if (url.startsWith("/api/library/quality")) {
        qualityCalls += 1;
        if (qualityCalls > 1) return new Promise<Response>((resolve) => { resolveRefresh = () => resolve(jsonResponse(REPORT) as Response); });
        return Promise.resolve(jsonResponse(REPORT) as Response);
      }
      if (url === "/api/lyrics/update") return new Promise<Response>((resolve) => { resolveLyrics = () => resolve(jsonResponse({ updated: true }) as Response); });
      throw new Error(`unexpected ${url}`);
    });
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Alpha");
    await user.click(screen.getByRole("checkbox", { name: "Выбрать: Alpha" }));
    await user.click(screen.getByRole("button", { name: "Тексты" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Обновить" }));

    expect(screen.getByRole("button", { name: "Тексты" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Тексты" }));
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/lyrics/update")).toHaveLength(1);
    resolveLyrics?.();
    expect(await screen.findByText("Обновление списка…")).toBeInTheDocument();
    resolveRefresh?.();
    await waitFor(() => expect(screen.getByRole("button", { name: "Тексты" })).not.toBeDisabled());
  });

  it("массово обновляет тексты не более чем тремя запросами одновременно", async () => {
    const report = {
      ...REPORT,
      tracks: Array.from({ length: 4 }, (_, i) => ({
        path: `/lib/${i}.mp3`, title: `Трек ${i}`, artist: "", album: "",
        issues: [{ category: "missing", message: "нет текста" }], changes: [],
      })),
    };
    const pending: (() => void)[] = [];
    fetchMock.mockImplementation((url: string) => {
      if (url.startsWith("/api/library/quality")) return Promise.resolve(jsonResponse(report) as Response);
      if (url === "/api/lyrics/update") return new Promise<Response>((resolve) => {
        pending.push(() => resolve(jsonResponse({ updated: true }) as Response));
      });
      throw new Error(`unexpected ${url}`);
    });
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Трек 0");
    for (let i = 0; i < 4; i++) await user.click(screen.getByRole("checkbox", { name: `Выбрать: Трек ${i}` }));
    await user.click(screen.getByRole("button", { name: "Тексты" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Обновить" }));

    await waitFor(() => expect(pending).toHaveLength(3));
    pending.shift()?.();
    await waitFor(() => expect(pending).toHaveLength(3));
    pending.splice(0).forEach((resolve) => resolve());
  });

  it("«Редактор» на карточке открывает единый редактор", async () => {
    const user = userEvent.setup();
    renderScreen();
    await screen.findByText("Alpha");
    const cardA = document.querySelector('.quality-track[data-path="/lib/a.mp3"]')!;
    await user.click(within(cardA as HTMLElement).getByRole("button", { name: "Редактор" }));
    await waitFor(() =>
      expect(trackEditorDialog).toHaveBeenCalledWith("/lib/a.mp3", "", null, null, { autoFetch: true }),
    );
    void trackBatchEditorDialog;
  });

  /* Сканирование библиотеки — секунды на реальной коллекции: вместо
     текстовой строки «Сканирование...» скелетон повторяет строки отчёта
     (.quality-track: чекбокс · название/мета · пилюли · действия) —
     без провала высоты при появлении списка. */
  it("пока отчёт грузится — скелетон строк .quality-track, не текст-загрузка", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    renderScreen();

    const rows = document.querySelectorAll(".quality-skeleton .quality-track");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((r) => {
      expect(r.querySelector(".quality-check .skeleton")).toBeTruthy();
      expect(r.querySelector(".quality-track-title .skeleton")).toBeTruthy();
      expect(r.querySelector(".quality-issues .skeleton")).toBeTruthy();
      expect(r.querySelector(".quality-actions .skeleton")).toBeTruthy();
    });
    /* Инертен: реальных строк и контролов до ответа нет, текст-загрузки нет. */
    expect(document.querySelectorAll(".quality-track").length).toBe(rows.length);
    expect(screen.queryByText("Сканирование библиотеки...")).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Выбрать: Alpha" })).toBeNull();
  });
});
