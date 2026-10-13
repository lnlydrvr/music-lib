import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { get, post } from "../src/lib/api";
import {
  startJob,
  JobError,
  waitJob,
  type RecommendationItem,
  type RecommendationProgress,
} from "../src/lib/jobs";
import { useDownloads } from "../src/stores/downloads";

/* api и стор загрузок изолируем: тестируем только SSE/опрос логику jobs.ts. */
vi.mock("../src/lib/api", () => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../src/stores/downloads", () => {
  const state = {
    track: vi.fn(),
    progress: vi.fn(),
    finish: vi.fn(),
    titleFor: vi.fn((_endpoint: string, title?: string) => title ?? "Заголовок"),
  };
  return { useDownloads: { getState: () => state } };
});

/* EventSource-заглушка: ручная доставка onmessage/onopen/onerror. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }

  emit(data: unknown): void {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  open(): void {
    this.onopen?.();
  }

  fail(): void {
    this.onerror?.();
  }
}

/* Snapshot kind=recommendations — как в progress-событии бэкенда.
   Item — точный DTO `_candidate_from_ytm` + seed: все поля обязательные string. */
function item(over: Partial<RecommendationItem> = {}): RecommendationItem {
  return {
    video_id: "dQw4w9WgXcQ",
    artist: "A",
    title: "T1",
    album: "Album A",
    cover_url: "https://example.com/cov.jpg",
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    seed: "Artist X — Song Y",
    ...over,
  };
}

function snap(over: Partial<RecommendationProgress> = {}): RecommendationProgress {
  return {
    type: "progress",
    kind: "recommendations",
    msg: "Обработан сид 1 из 3",
    seed_index: 1,
    seed_count: 3,
    seed: "Artist X — Song Y",
    items: [item()],
    seeds: 3,
    library_count: 42,
    total: 1,
    ...over,
  };
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  /* reset, не clear: сбрасывает и очередь mockResolvedValueOnce между тестами */
  vi.resetAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function lastEs(): FakeEventSource {
  const es = FakeEventSource.instances[FakeEventSource.instances.length - 1];
  if (!es) throw new Error("EventSource не создан");
  return es;
}

describe("waitJob: SSE-события", () => {
  it("terminal done из SSE закрывает поток и получает итог polling-опросом", async () => {
    vi.mocked(get).mockResolvedValue({ status: "done", result: { updated: 2 } });
    const p = waitJob("sse-done");
    const es = lastEs();

    es.emit({ type: "done" });

    await vi.advanceTimersByTimeAsync(0);
    await expect(p).resolves.toEqual({ updated: 2 });
    expect(es.closed).toBe(true);
    expect(get).toHaveBeenCalledWith("/api/jobs/sse-done");
  });

  it("terminal error из SSE реджектит с ошибкой задачи без polling", async () => {
    const p = waitJob("sse-error");
    const es = lastEs();

    es.emit({ type: "error", error: "Задача не выполнена" });

    await expect(p).rejects.toThrow("Задача не выполнена");
    expect(es.closed).toBe(true);
    expect(get).not.toHaveBeenCalled();
  });

  it("kind=recommendations вызывает и onProgress, и onRecommendations", async () => {
    const onProgress = vi.fn();
    const onRec = vi.fn();
    void waitJob("j1", onProgress, onRec);
    const es = lastEs();

    es.emit(snap());
    await vi.advanceTimersByTimeAsync(0);

    expect(onProgress).toHaveBeenCalledTimes(1);
    expect(onRec).toHaveBeenCalledTimes(1);
    const arg = onRec.mock.calls[0][0] as RecommendationProgress;
    expect(arg).toMatchObject({
      type: "progress",
      kind: "recommendations",
      msg: "Обработан сид 1 из 3",
      seed_index: 1,
      seed_count: 3,
      seed: "Artist X — Song Y",
      items: [item()],
      seeds: 3,
      library_count: 42,
      total: 1,
    });
  });

  it("обычный progress — только onProgress, onRecommendations молчит", async () => {
    const onProgress = vi.fn();
    const onRec = vi.fn();
    void waitJob("j2", onProgress, onRec);
    const es = lastEs();

    es.emit({ type: "progress", percent: 20, msg: "Сканирование библиотеки..." });
    await vi.advanceTimersByTimeAsync(0);

    expect(onProgress).toHaveBeenCalledTimes(1);
    expect(onProgress).toHaveBeenCalledWith({ type: "progress", percent: 20, msg: "Сканирование библиотеки...", message: "Сканирование библиотеки..." });
    expect(onRec).not.toHaveBeenCalled();
  });

  it("повторные kind=recommendations допустимы: оба колбэка на каждый snapshot", async () => {
    const onProgress = vi.fn();
    const onRec = vi.fn();
    void waitJob("j3", onProgress, onRec);
    const es = lastEs();

    es.emit(snap());
    es.emit(
      snap({
        msg: "Обработан сид 2 из 3",
        seed_index: 2,
        items: [
          item(),
          item({
            video_id: "abc123YTM",
            artist: "B",
            title: "T2",
            album: "",
            cover_url: "",
            url: "https://www.youtube.com/watch?v=abc123YTM",
            seed: "Artist Z — Song W",
          }),
        ],
        total: 2,
      }),
    );
    await vi.advanceTimersByTimeAsync(0);

    expect(onRec).toHaveBeenCalledTimes(2);
    const second = onRec.mock.calls[1][0] as RecommendationProgress;
    expect(second.seed_index).toBe(2);
    expect(second.items).toHaveLength(2);
    expect(second.items[1]).toEqual({
      video_id: "abc123YTM",
      artist: "B",
      title: "T2",
      album: "",
      cover_url: "",
      url: "https://www.youtube.com/watch?v=abc123YTM",
      seed: "Artist Z — Song W",
    });
    expect(second.total).toBe(2);
    expect(onProgress).toHaveBeenCalledTimes(2);
  });

  it("неизвестные SSE-события игнорируются", async () => {
    const onProgress = vi.fn();
    void waitJob("j4", onProgress);
    lastEs().emit({ type: "end" });
    await vi.advanceTimersByTimeAsync(0);
    expect(onProgress).not.toHaveBeenCalled();
  });
});

describe("waitJob: обрыв SSE и polling-фолбэк", () => {
  it("SSE error закрывает EventSource, результат приходит опросом (done)", async () => {
    vi.mocked(get).mockResolvedValue({ status: "done", result: { items: [], total: 0 } });
    const p = waitJob("j5");
    const es = lastEs();

    es.fail();
    expect(es.closed).toBe(true);

    await vi.advanceTimersByTimeAsync(0);
    await expect(p).resolves.toEqual({ items: [], total: 0 });
  });

  it("SSE error → polling error: реджект с сообщением задачи, поток закрыт", async () => {
    vi.mocked(get).mockResolvedValue({ status: "error", error: "Радио недоступно" });
    const p = waitJob("j5b");
    const es = lastEs();

    es.fail();
    expect(es.closed).toBe(true);

    const assertion = expect(p).rejects.toThrow("Радио недоступно");
    await vi.advanceTimersByTimeAsync(0);
    await assertion;
    expect(es.closed).toBe(true);
  });

  it("polling передаёт последний progress snapshot рекомендаций после обрыва SSE", async () => {
    const onProgress = vi.fn();
    const onRec = vi.fn();
    const snapshot = snap({
      message: { code: "jobs.recommend.name", params: { count: 2 }, message: "Two recommendations" },
      seed: "Artist Z — Song W",
      items: [item(), item({ video_id: "next", title: "T2" })],
      total: 2,
    });
    vi.mocked(get)
      .mockResolvedValueOnce({ status: "running", progress: [snapshot] })
      .mockResolvedValueOnce({ status: "done", result: "ok" });
    const p = waitJob("poll-progress", onProgress, onRec);

    lastEs().fail();
    await vi.advanceTimersByTimeAsync(0);

    expect(onProgress).toHaveBeenCalledWith(snapshot);
    expect(onRec).toHaveBeenCalledWith(snapshot);
    await vi.advanceTimersByTimeAsync(300);
    await expect(p).resolves.toBe("ok");
  });

  it("polling после открытого SSE не дублирует уже доставленный progress snapshot", async () => {
    const onProgress = vi.fn();
    const onRec = vi.fn();
    const snapshot = snap();
    vi.mocked(get)
      .mockResolvedValueOnce({ status: "running", progress: [snapshot] })
      .mockResolvedValueOnce({ status: "done", result: "ok" });
    const p = waitJob("open-stream", onProgress, onRec);
    const es = lastEs();

    es.emit(snapshot);
    es.open();
    await vi.advanceTimersByTimeAsync(0);

    expect(onProgress).toHaveBeenCalledTimes(1);
    expect(onRec).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(300);
    await expect(p).resolves.toBe("ok");
  });

  it("polling: done резолвит промис и закрывает поток", async () => {
    vi.mocked(get).mockResolvedValue({ status: "done", result: 42 });
    const p = waitJob("j6");
    const es = lastEs();

    es.open();
    await vi.advanceTimersByTimeAsync(0);

    await expect(p).resolves.toBe(42);
    expect(es.closed).toBe(true);
  });

  it("polling: error реджектит с сообщением задачи", async () => {
    vi.mocked(get).mockResolvedValue({ status: "error", error: "Радио недоступно" });
    const p = waitJob("j7");
    lastEs().open();
    const assertion = expect(p).rejects.toThrow("Радио недоступно");

    await vi.advanceTimersByTimeAsync(0);
    await assertion;
  });

  it("polling сохраняет descriptor terminal error для вызывающего кода", async () => {
    const descriptor = { code: "jobs.errors.rate_limited", params: { retryAfter: 30 }, message: "Try again in 30 seconds" };
    vi.mocked(get).mockResolvedValue({ status: "error", error: descriptor });
    const p = waitJob("j7-structured");
    lastEs().open();
    const assertion = expect(p).rejects.toMatchObject({
      renderableMessage: descriptor,
    } satisfies Partial<JobError>);
    await vi.advanceTimersByTimeAsync(0);

    await assertion;
  });

  it("polling: активная задача опрашивается повторно через 300 мс", async () => {
    vi.mocked(get)
      .mockResolvedValueOnce({ status: "running" })
      .mockResolvedValueOnce({ status: "done", result: "ok" });
    const p = waitJob("j8");
    lastEs().open();

    await vi.advanceTimersByTimeAsync(0);
    expect(get).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(300);
    await expect(p).resolves.toBe("ok");
    expect(get).toHaveBeenCalledTimes(2);
  });
});

describe("startJob: проброс колбэков и трекинг", () => {
  it("onRecommendations и onProgress доходят до SSE, задача трекается доком", async () => {
    vi.mocked(post).mockResolvedValue({ job_id: "job-9" });
    vi.mocked(get).mockResolvedValue({ status: "done", result: { items: [], total: 0 } });
    const onProgress = vi.fn();
    const onRec = vi.fn();

    const p = startJob("/api/recommend/generate", {}, { onProgress, onRecommendations: onRec, title: "Рекомендации" });
    await vi.advanceTimersByTimeAsync(0); // post → waitJob → EventSource
    const es = lastEs();
    expect(es.url).toBe("/api/jobs/job-9/events");

    es.emit(snap());
    await vi.advanceTimersByTimeAsync(0);
    expect(onRec).toHaveBeenCalledTimes(1);
    expect(onProgress).toHaveBeenCalledTimes(1);

    es.open();
    await vi.advanceTimersByTimeAsync(0);
    await expect(p).resolves.toEqual({ items: [], total: 0 });

    const dl = useDownloads.getState();
    expect(dl.track).toHaveBeenCalledWith("job-9", "Рекомендации");
    expect(dl.finish).toHaveBeenCalledWith("job-9", true, { code: "jobs.common.done", message: "Done" });
  });

  it("ошибка задачи завершает док как ошибку и реджектит промис", async () => {
    vi.mocked(post).mockResolvedValue({ job_id: "job-10" });
    vi.mocked(get).mockResolvedValue({ status: "error", error: "Нет YT Music" });

    const p = startJob("/api/recommend/generate", {});
    const assertion = expect(p).rejects.toThrow("Нет YT Music");
    await vi.advanceTimersByTimeAsync(0);
    lastEs().open();
    await vi.advanceTimersByTimeAsync(0);
    await assertion;

    expect(useDownloads.getState().finish).toHaveBeenCalledWith("job-10", false, "Нет YT Music");
  });

  it("сохраняет structured terminal error в доке без рендеринга в строку", async () => {
    vi.mocked(post).mockResolvedValue({ job_id: "job-structured-error" });
    const descriptor = {
      code: "jobs.errors.rate_limited",
      params: { retryAfter: 30 },
      message: "Try again in 30 seconds",
    };
    const p = startJob("/api/recommend/generate", {});
    await vi.advanceTimersByTimeAsync(0);

    lastEs().emit({ type: "error", error: descriptor });

    await expect(p).rejects.toThrow();
    expect(useDownloads.getState().finish).toHaveBeenCalledWith(
      "job-structured-error",
      false,
      descriptor,
    );
  });
});
