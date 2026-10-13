import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { useDownloads } from "../src/stores/downloads";
import { DownloadsDock } from "../src/components/DownloadsDock";
import { changeLanguage } from "../src/i18n";

function jsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => body,
    headers: { get: () => "application/json" },
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  useDownloads.setState({ items: {}, expanded: false });
  fetchMock = vi.fn(async (url: unknown) =>
    jsonResponse(String(url).startsWith("/api/jobs?") ? [] : {}),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("downloads store", () => {
  it("показывает счётчик активной загрузки только в label", () => {
    useDownloads.setState({
      expanded: false,
      items: {
        active: {
          id: "active",
          title: "Скачивание трека",
          name: "",
          status: "active",
          percent: 42,
          msg: "Скачивание",
          addedAt: 1,
        },
      },
    });
    const { container } = render(createElement(DownloadsDock));

    expect(container.querySelector(".dl-count")).not.toBeInTheDocument();
    expect(screen.getByText("Загрузки · 1 · 42%")).toBeInTheDocument();
  });

  it("не дублирует одинаковые или пустые title/name в строке задачи", () => {
    useDownloads.setState({
      expanded: true,
      items: {
        same: { id: "same", title: "YouTube Music — скачивание", name: "YouTube Music — скачивание", status: "active", percent: 10, msg: "Скачивание", addedAt: 4 },
        noName: { id: "noName", title: "Скачивание трека", name: "", status: "active", percent: 10, msg: "Скачивание", addedAt: 3 },
        noTitle: { id: "noTitle", title: "", name: "Название трека", status: "active", percent: 10, msg: "Скачивание", addedAt: 2 },
        different: { id: "different", title: "Скачивание трека", name: "Название трека", status: "active", percent: 10, msg: "Скачивание", addedAt: 1 },
      },
    });
    const { container } = render(createElement(DownloadsDock));

    expect([...container.querySelectorAll(".dl-item-title")].map((element) => element.textContent)).toEqual([
      "YouTube Music — скачивание",
      "Скачивание трека",
      "Название трека",
      "Скачивание трека · Название трека",
    ]);
  });

  it("показывает длинные title и subtitle рядом с icon-only закрытием", () => {
    const title = "[8/21] The Neighbourhood — Livin' In a Dream (feat. Nipsey Hussle)";
    useDownloads.setState({
      expanded: true,
      items: {
        long: { id: "long", title, name: "YouTube Music — скачивание", status: "active", percent: 10, msg: "Скачивание аудио высокого качества", addedAt: 1 },
      },
    });
    const { container } = render(createElement(DownloadsDock));

    expect(screen.getByText(`${title} · YouTube Music — скачивание`)).toHaveClass("dl-item-title");
    expect(screen.getByText("Скачивание аудио высокого качества")).toHaveClass("dl-item-sub");
    const dismiss = screen.getByRole("button", { name: `Убрать: ${title}` });
    expect(dismiss).toHaveClass("iconbtn");
    expect(dismiss.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelector(".dl-item-main + .dl-item-dismiss")).toBe(dismiss);
  });

  it("рендерит раскрытие и очистку отдельными native-кнопками", async () => {
    fetchMock.mockImplementation(async (url: unknown) =>
      jsonResponse(String(url).startsWith("/api/jobs?") ? [] : {}),
    );
    useDownloads.getState().track("dock-job", "Загрузка");
    useDownloads.getState().finish("dock-job", true);
    useDownloads.setState({ expanded: true });
    render(createElement(DownloadsDock));

    const toggle = screen.getByRole("button", { name: /Загрузки: свернуть/ });
    const clear = screen.getByRole("button", { name: "Убрать завершённые задачи" });
    expect(toggle).toHaveAttribute("aria-controls", "dl-panel");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(clear.closest("button")).toBe(clear);

    fireEvent.click(clear);
    await vi.advanceTimersByTimeAsync(300);
    expect(screen.queryByRole("button", { name: "Убрать завершённые задачи" })).not.toBeInTheDocument();
  });

  it("track → progress → finish: автоскрытие успешного через 5 сек", async () => {
    const st = useDownloads.getState();
    st.track("job-1", "Скачивание трека");
    let item = useDownloads.getState().items["job-1"];
    expect(item).toMatchObject({ status: "active", msg: { code: "jobs.dock.launching", message: "Starting…" }, percent: null });

    useDownloads.getState().progress("job-1", { percent: 40, msg: "Скачиваю" });
    item = useDownloads.getState().items["job-1"];
    expect(item.percent).toBe(40);
    expect(item.msg).toBe("Скачиваю");

    useDownloads.getState().finish("job-1", true);
    item = useDownloads.getState().items["job-1"];
    expect(item.status).toBe("done");
    expect(item.percent).toBe(100);
    expect(item.msg).toEqual({ code: "jobs.common.done", message: "Done" });

    // 5 сек — автоскрытие (плюс 180 мс анимации выхода).
    await vi.advanceTimersByTimeAsync(5200);
    expect(useDownloads.getState().items["job-1"]).toBeUndefined();
  });

  it("ошибка остаётся в доке", async () => {
    useDownloads.getState().track("job-2", "Рекомендации");
    useDownloads.getState().finish("job-2", false, "Сеть недоступна");
    await vi.advanceTimersByTimeAsync(10000);
    expect(useDownloads.getState().items["job-2"]?.status).toBe("error");
  });

  it("track автоматически раскрывает панель", () => {
    expect(useDownloads.getState().expanded).toBe(false);
    useDownloads.getState().track("job-3", "Сжатие");
    expect(useDownloads.getState().expanded).toBe(true);
    expect(localStorage.getItem("music-lib-dl-expanded")).toBe("1");
  });

  it("track подтягивает имя задачи с бэкенда", async () => {
    fetchMock.mockImplementation(async (url: unknown) =>
      jsonResponse(String(url).includes("/api/jobs/name-1") ? { name: "Песня дня" } : {}),
    );
    useDownloads.getState().track("name-1", "Скачивание трека");
    await vi.waitFor(() => {
      expect(useDownloads.getState().items["name-1"]?.name).toBe("Песня дня");
    });
  });

  it("clearFinished убирает завершённые, активные остаются", async () => {
    const st = useDownloads.getState();
    st.track("a1", "A");
    st.track("a2", "B");
    st.finish("a2", true);
    st.clearFinished();
    await vi.advanceTimersByTimeAsync(300);
    expect(Object.keys(useDownloads.getState().items)).toEqual(["a1"]);
  });

  it("restore: ошибки всегда, done свежее 5 мин, активные пропускаются", async () => {
    const now = Date.now() / 1000;
    fetchMock.mockImplementation(async (url: unknown) =>
      jsonResponse(
        String(url).startsWith("/api/jobs?")
          ? [
              { id: "fresh", name: "Свежая", status: "done", created_at: now - 60 },
              { id: "stale", name: "Старая", status: "done", created_at: now - 400 },
              { id: "err", name: "Сломалась", status: "error", error: "Нет места" },
              { id: "live", name: "Живая", status: "active" },
            ]
          : {},
      ),
    );
    await useDownloads.getState().restore();
    const items = useDownloads.getState().items;
    expect(Object.keys(items).sort()).toEqual(["err", "fresh"]);
    expect(items.err.msg).toBe("Нет места");
    expect(items.fresh.status).toBe("done");
  });

  it("titleFor: приоритет явного заголовка, префиксы эндпоинтов, дефолт", () => {
    const t = useDownloads.getState().titleFor;
    expect(t("/api/download", "Мой заголовок")).toBe("Мой заголовок");
    expect(t("/api/download/batch")).toMatchObject({ code: "jobs.download.batch_name" });
    expect(t("/api/download?x=1")).toMatchObject({ code: "jobs.download.name" });
    expect(t("/api/ytmusic/download")).toMatchObject({ code: "jobs.ytm.name" });
    expect(t("/api/unknown/thing")).toMatchObject({ code: "jobs.dock.fallback_name" });
  });

  it("хранит descriptor задачи и переводит его при смене языка", async () => {
    useDownloads.getState().track("localized", { code: "jobs.download.name", message: "Download" });
    useDownloads.getState().progress("localized", { message: { code: "jobs.common.done", message: "Done" } });
    useDownloads.setState({ expanded: true });
    render(createElement(DownloadsDock));

    await changeLanguage("en");
    expect(screen.getByText("Download")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    await changeLanguage("ru");
    expect(screen.getByText("Скачивание")).toBeInTheDocument();
    expect(screen.getByText("Готово")).toBeInTheDocument();
  });
});
