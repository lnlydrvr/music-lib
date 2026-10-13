import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  TrackEditor,
  type EditorRecord,
  type TrackEditorHandle,
  type TrackEditorProps,
  type TrackTags,
} from "../src/features/editor";
import { toast } from "../src/lib/toast";
import { changeLanguage } from "../src/i18n";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

const TAGS: TrackTags = {
  title: "Old Title",
  artist: "Old Artist",
  album: "Old Album",
  year: "1999",
  has_cover: false,
};

function renderEditor(props: Partial<TrackEditorProps> & { path: string }) {
  const ref = { current: null as TrackEditorHandle | null };
  const utils = render(
    <TrackEditor
      ref={(h) => {
        ref.current = h;
      }}
      autoFetch={false}
      records={null}
      {...props}
    />,
  );
  return { ref, ...utils };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(toast).mockClear();
});

describe("TrackEditor", () => {
  it("поля из тегов; чип-подсказка и diff «было → стало»; чип возвращает значение", async () => {
    const user = userEvent.setup();
    renderEditor({ path: "/lib/a.mp3", current: TAGS });
    const input = screen.getByLabelText("Название");
    expect(input).toHaveValue("Old Title");
    expect(screen.queryByRole("button", { name: /Вернуть исходное/ })).not.toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "New Title");
    const chip = screen.getByRole("button", { name: "Вернуть исходное значение поля Название" });
    expect(chip).toHaveTextContent("Old Title");

    const oldLine = input.closest(".field-input")!.querySelector(".field-old")!;
    expect(within(oldLine as HTMLElement).getByText("Old")).toBeInTheDocument();
    expect(within(oldLine as HTMLElement).getByText("New")).toBeInTheDocument();

    await user.click(chip);
    expect(input).toHaveValue("Old Title");
    expect(screen.queryByRole("button", { name: /Вернуть исходное/ })).not.toBeInTheDocument();
  });

  it("выбор записи источника заполняет поля; пустые поля записи — из файла", async () => {
    const user = userEvent.setup();
    const rec: EditorRecord = {
      source: "itunes",
      title: "New Title",
      artist: "New Artist",
      album: "Album X",
      label: "UMG",
    };
    const { ref } = renderEditor({ path: "/lib/a.mp3", current: TAGS, records: [rec] });
    const card = screen.getByRole("button", { name: "Выбрать источник: New Title — New Artist — Album X" });
    await user.click(card);
    expect(card).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Название")).toHaveValue("New Title");
    expect(screen.getByLabelText("Исполнитель")).toHaveValue("New Artist");
    expect(screen.getByLabelText("Альбом")).toHaveValue("Album X");
    // publisher без значения — фолбэк на label записи.
    expect(screen.getByLabelText("Издатель / Лейбл")).toHaveValue("UMG");
    // Поле, которого у записи нет, остаётся из файла.
    expect(screen.getByLabelText("Год")).toHaveValue("1999");
    expect(ref.current!.isDirty()).toBe(true);
    expect(ref.current!.selectedRecord()).toBe(rec);
  });

  it("валидация при сохранении: toast, ошибка у поля, сеть не трогаем", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { ref } = renderEditor({ path: "/lib/a.mp3", current: TAGS });
    await userEvent.setup().type(screen.getByLabelText("Год"), "20");

    let r: TrackTags | false | undefined;
    await act(async () => {
      r = await ref.current!.save();
    });
    expect(r).toBe(false);
    expect(toast).toHaveBeenCalledWith({
      code: "library.album_detail.invalid_field",
      params: { field: "Год", message: "Год должен состоять из 4 цифр, например 2024" },
    }, "error");
    expect(screen.getByText("Год должен состоять из 4 цифр, например 2024")).toBeInTheDocument();
    expect(screen.getByLabelText("Год")).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("успешное сохранение: payload /api/tags/apply, toast, dirty сброшен", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      expect(url).toBe("/api/tags/apply");
      return jsonResponse({ ...TAGS, title: "New Title", has_cover: true });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { ref } = renderEditor({ path: "/lib/a.mp3", current: TAGS });
    const user = userEvent.setup();
    await user.clear(screen.getByLabelText("Название"));
    await user.type(screen.getByLabelText("Название"), "New Title");

    let r: TrackTags | false | undefined;
    await act(async () => {
      r = await ref.current!.save();
    });
    expect(r).toMatchObject({ title: "New Title", has_cover: true });
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toMatchObject({
      path: "/lib/a.mp3",
      source: "",
      cover_url: "",
      thumbnail_url: "",
      apply_cover: true,
    });
    expect(body.fields).toMatchObject({ title: "New Title", artist: "Old Artist", year: "1999" });
    expect(toast).toHaveBeenCalledWith({ code: "editor.saved" });
    expect(ref.current!.isDirty()).toBe(false);
    // Исходные значения = записанные: чип-подсказка исчезла.
    expect(screen.queryByRole("button", { name: /Вернуть исходное/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Название")).toHaveValue("New Title");
  });

  it("серверные ошибки полей подсвечиваются", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Проверьте поля", errors: { year: "Год: 4 цифры" } }, 400)),
    );
    const { ref } = renderEditor({ path: "/lib/a.mp3", current: TAGS });
    let r: TrackTags | false | undefined;
    await act(async () => {
      r = await ref.current!.save();
    });
    expect(r).toBe(false);
    expect(toast).toHaveBeenCalledWith("Проверьте поля", "error");
    expect(screen.getByText("Год: 4 цифры")).toBeInTheDocument();
    expect(screen.getByLabelText("Год")).toHaveAttribute("aria-invalid", "true");
  });

  it("applyAlbumFallback: клон «Теги альбома» — общие поля записи, трековые из файла", async () => {
    const rec: EditorRecord = {
      source: "itunes",
      title: "T",
      artist: "AR",
      album: "AL",
      year: "2001",
      track_number: "5",
    };
    const { ref } = renderEditor({ path: "/lib/a.mp3", current: TAGS, records: [rec] });
    act(() => {
      ref.current!.applyAlbumFallback(rec);
    });
    const card = screen.getByRole("button", { name: "Выбрать источник: Теги альбома: AL" });
    expect(card).toHaveAttribute("aria-pressed", "true");
    expect(card.className).toContain("album-fallback");
    // Альбомные поля — из записи, трековые (title/artist/track) — из файла.
    expect(screen.getByLabelText("Альбом")).toHaveValue("AL");
    expect(screen.getByLabelText("Год")).toHaveValue("2001");
    expect(screen.getByLabelText("Название")).toHaveValue("Old Title");
    expect(screen.getByLabelText("Исполнитель")).toHaveValue("Old Artist");
    expect(screen.getByLabelText("№ трека")).toHaveValue("");
    expect(ref.current!.records()).toHaveLength(2); // запись + клон
    expect(ref.current!.isDirty()).toBe(true);
  });

  it("превью обложки: thumbnail, чекбокс «Применить обложку», «Обложка не найдена»", () => {
    // Есть превью источника — flow «текущая → новая» без текущей обложки (♫).
    const first = renderEditor({ path: "/lib/a.mp3", current: TAGS, thumbnailUrl: "http://t/1.jpg" });
    expect(screen.getByAltText("Обложка выбранного источника")).toHaveAttribute("src", "http://t/1.jpg");
    expect(screen.getByTitle("Текущая обложка").querySelector(".lib-nocover")).toBeTruthy();
    expect(screen.getByRole("checkbox")).toBeChecked();
    first.unmount();

    // Текущая обложка файла — /api/cover.
    const second = renderEditor({
      path: "/lib/a.mp3",
      current: { ...TAGS, has_cover: true },
      thumbnailUrl: "http://t/1.jpg",
    });
    expect(screen.getByAltText("Текущая обложка трека")).toHaveAttribute(
      "src",
      "/api/cover?path=%2Flib%2Fa.mp3",
    );
    second.unmount();

    const third = renderEditor({ path: "/lib/a.mp3", current: TAGS });
    expect(screen.getByText("Обложка не найдена")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    third.unmount();
  });

  it("changes all editor-owned UI copy when the active locale changes", async () => {
    await changeLanguage("en");
    renderEditor({ path: "/lib/a.mp3", current: TAGS, thumbnailUrl: "http://t/1.jpg" });

    expect(screen.getByText("Cover")).toBeInTheDocument();
    expect(screen.getByTitle("Current cover")).toBeInTheDocument();
    expect(screen.getByAltText("Selected source cover")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Apply cover" })).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
  });
});
