import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import { metaflowStageMessage, runMetaflow, trackBatchEditorDialog, trackEditorDialog, type MetaflowStage } from "../src/features/editor";
import { toast } from "../src/lib/toast";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const TAGS_A = { title: "Alpha", artist: "Artist A", album: "Greatest", year: "2001", has_cover: false };
const TAGS_B = { title: "Beta", artist: "Artist B", album: "Greatest", year: "2001", has_cover: false };
/* genre есть только у записей источников — выбор записи меняет трек (dirty). */
const REC_A = { source: "itunes", title: "Alpha", artist: "Artist A", album: "Greatest", year: "2001", genre: "Rock", cover_url: "http://c/a.jpg" };
const REC_B = { source: "itunes", title: "Beta", artist: "Artist B", album: "Greatest", year: "2001", genre: "Rock" };

function makeFetch() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith("/api/tags?")) {
      const path = new URLSearchParams(url.split("?")[1]).get("path") || "";
      return jsonResponse(path.endsWith("a.mp3") ? TAGS_A : TAGS_B);
    }
    if (url === "/api/fetch/meta") {
      const body = JSON.parse(String(init?.body || "{}")) as { path?: string };
      return jsonResponse({ records: body.path?.endsWith("a.mp3") ? [REC_A] : [REC_B] });
    }
    if (url === "/api/tags/apply") {
      const body = JSON.parse(String(init?.body || "{}")) as { path?: string; fields?: Record<string, string> };
      return jsonResponse({ ...(body.path?.endsWith("a.mp3") ? TAGS_A : TAGS_B), ...body.fields });
    }
    if (url === "/api/lyrics/update") return jsonResponse({ updated: true });
    throw new Error(`unexpected ${url}`);
  });
}

/* Стенд: кнопка запускает диалог, итог пишется в res. */
function Host({ run, res }: { run: () => Promise<unknown>; res: (r: unknown) => void }) {
  return (
    <button onClick={() => void run().then(res)}>open</button>
  );
}

function openDialog(run: () => Promise<unknown>, res: (r: unknown) => void) {
  render(
    <DialogProvider>
      <Host run={run} res={res} />
    </DialogProvider>,
  );
  return screen.getByText("open");
}

const ENTRIES = [
  { path: "/lib/a.mp3", title: "Alpha", artist: "Artist A" },
  { path: "/lib/b.mp3", title: "Beta", artist: "Artist B" },
];

beforeEach(() => vi.mocked(toast).mockClear());
afterEach(() => vi.unstubAllGlobals());

describe("trackEditorDialog", () => {
  it("заголовок из тегов; Сохранить → POST и закрытие с обновлёнными тегами", async () => {
    const user = userEvent.setup();
    const fetchMock = makeFetch();
    vi.stubGlobal("fetch", fetchMock);
    const res = vi.fn();
    await user.click(openDialog(() => trackEditorDialog("/lib/a.mp3"), res));

    expect(screen.getByText("Редактор: Alpha")).toBeInTheDocument();
    expect(screen.getByLabelText("Название")).toHaveValue("Alpha");

    await user.clear(screen.getByLabelText("Год"));
    await user.type(screen.getByLabelText("Год"), "2002");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(res).lastCalledWith(expect.objectContaining({ year: "2002" })));
    const body = JSON.parse(String(fetchMock.mock.calls.find(([u]) => u === "/api/tags/apply")?.[1]?.body));
    expect(body.fields.year).toBe("2002");
    expect(screen.queryByText("Редактор: Alpha")).not.toBeInTheDocument();
  });

  it("ошибка чтения тегов → toast, без модалки, null", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.startsWith("/api/tags?")) return jsonResponse({ detail: "Не удалось прочитать теги" }, 500);
        throw new Error(`unexpected ${url}`);
      }),
    );
    const res = vi.fn();
    await user.click(openDialog(() => trackEditorDialog("/lib/a.mp3"), res));
    await waitFor(() => expect(res).lastCalledWith(null));
    expect(toast).toHaveBeenCalledWith("Не удалось прочитать теги", "error");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("trackBatchEditorDialog", () => {
  it("мастер-детейл: dirty-строка, «Готово» сохраняет только правленные", async () => {
    const user = userEvent.setup();
    const fetchMock = makeFetch();
    vi.stubGlobal("fetch", fetchMock);
    const res = vi.fn();
    await user.click(openDialog(() => trackBatchEditorDialog(ENTRIES), res));

    expect(screen.getByText("Массовое редактирование метаданных")).toBeInTheDocument();
    const listbox = screen.getByRole("listbox", { name: "Треки для редактирования" });
    expect(within(listbox).getAllByRole("option")).toHaveLength(2);
    // Первый трек открыт, второй предзагружен фоном.
    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([u]) => u === "/api/fetch/meta")).toHaveLength(2),
    );

    // Выбор записи у первого трека — строка помечается изменённой.
    await user.click(screen.getByRole("button", { name: "Выбрать источник: Alpha — Artist A — Greatest" }));
    const first = within(listbox).getAllByRole("option")[0];
    await waitFor(() => expect(first).toHaveAttribute("aria-label", "Alpha — Artist A (есть несохранённые изменения)"));

    await user.click(screen.getByRole("button", { name: "Готово" }));
    await waitFor(() =>
      expect(res).lastCalledWith({
        "/lib/a.mp3": expect.objectContaining({ title: "Alpha" }),
      }),
    );
    // Второй трек не правился — без запроса apply.
    expect(fetchMock.mock.calls.filter(([u]) => u === "/api/tags/apply")).toHaveLength(1);
    expect(toast).toHaveBeenCalledWith({ code: "editor.batch.saved", params: { count: 1 } });
  });

  it("«Применить ко всем трекам» без выбора — warn; с выбором — разнос на все треки", async () => {
    const user = userEvent.setup();
    const fetchMock = makeFetch();
    vi.stubGlobal("fetch", fetchMock);
    const res = vi.fn();
    await user.click(openDialog(() => trackBatchEditorDialog(ENTRIES), res));

    // Без выбранного источника — подсказка.
    await user.click(screen.getByRole("button", { name: "Применить выбранный источник ко всем трекам" }));
    expect(toast).toHaveBeenCalledWith({ code: "editor.batch.select_source_first" }, "warn");

    // Выбираем источник текущего трека…
    await user.click(screen.getByRole("button", { name: "Выбрать источник: Alpha — Artist A — Greatest" }));
    // …переключаемся на второй (поля второго смонтированы)…
    await user.click(within(screen.getByRole("listbox")).getAllByRole("option")[1]);
    const hostB = document.querySelector('[data-path="/lib/b.mp3"]');
    await waitFor(() => expect(hostB).toBeTruthy());
    expect(within(hostB as HTMLElement).getByLabelText("Название")).toHaveValue("Beta");
    // …возвращаемся к первому и разносим источник.
    await user.click(within(screen.getByRole("listbox")).getAllByRole("option")[0]);
    await user.click(screen.getByRole("button", { name: "Применить выбранный источник ко всем трекам" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ code: "editor.batch.applied", params: { applied: 2, failed: 0 } }, ""));

    const listbox = screen.getByRole("listbox", { name: "Треки для редактирования" });
    await waitFor(() => expect(within(listbox).getAllByRole("option")[1]).toHaveAttribute("aria-label", "Beta — Artist B (есть несохранённые изменения)"));

    await user.click(screen.getByRole("button", { name: "Готово" }));
    await waitFor(() =>
      expect(res).lastCalledWith({
        "/lib/a.mp3": expect.objectContaining({ title: "Alpha" }),
        "/lib/b.mp3": expect.objectContaining({ title: "Beta" }),
      }),
    );
    expect(toast).toHaveBeenCalledWith({ code: "editor.batch.saved", params: { count: 2 } });
    expect(fetchMock.mock.calls.filter(([u]) => u === "/api/tags/apply")).toHaveLength(2);
  });
});

describe("runMetaflow", () => {
  it("maps each typed stage to a renderable localized message", () => {
    expect(metaflowStageMessage("metadata")).toEqual({ code: "search.metaflow.metadata_searching" });
    expect(metaflowStageMessage("lyrics")).toEqual({ code: "search.metaflow.lyrics_updating" });
  });

  it("после диалога молча обновляет текст (LRCLIB); отмена → false", async () => {
    const user = userEvent.setup();
    const fetchMock = makeFetch();
    vi.stubGlobal("fetch", fetchMock);
    const res = vi.fn();
    const steps: MetaflowStage[] = [];
    await user.click(
      openDialog(() => runMetaflow("/lib/a.mp3", "http://t/1.jpg", (m) => steps.push(m)), res),
    );
    expect(steps[0]).toBe("metadata");

    await user.click(screen.getByRole("button", { name: "Отмена" }));
    await waitFor(() => expect(res).lastCalledWith(false));
    expect(steps).toEqual(["metadata", "lyrics"]);
    expect(fetchMock.mock.calls.some(([u]) => u === "/api/lyrics/update")).toBe(true);
  });

  it("сохранение в диалоге → true", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", makeFetch());
    const res = vi.fn();
    await user.click(openDialog(() => runMetaflow("/lib/a.mp3"), res));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(res).lastCalledWith(true));
  });
});
