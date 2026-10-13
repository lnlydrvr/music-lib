import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { clearMetaCache, useMetaSources } from "../src/features/editor";
import { toast } from "../src/lib/toast";
import { ApiError } from "../src/lib/api";

vi.mock("../src/lib/toast", () => ({ toast: vi.fn(), toastEx: vi.fn() }));

const ITUNES = { source: "itunes", title: "Track A", artist: "Artist A", album: "Album A" };
const DISCOGS = { source: "discogs", title: "Track A", artist: "Artist A", album: "Album D" };

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { resolve, promise };
}

const SETTINGS = {
  metadata_sources: ["itunes", "discogs"],
  metadata_sources_available: ["itunes", "deezer", "discogs"],
};

function postBody(init?: RequestInit) {
  return JSON.parse(String(init?.body || "{}")) as Record<string, unknown>;
}

beforeEach(() => {
  clearMetaCache();
  vi.mocked(toast).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useMetaSources", () => {
  it("источники догружаются по мере ответа, pending — летящие", async () => {
    const slow = deferred<{ records: unknown[] }>();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/settings") return jsonResponse(SETTINGS);
      if (url === "/api/fetch/meta") {
        // Каждый запрос — ровно один источник (фильтр sources).
        const body = postBody(init);
        expect(body.sources).toEqual([expect.stringMatching(/itunes|discogs/)]);
        return body.sources?.[0] === "itunes"
          ? jsonResponse({ records: [ITUNES] })
          : jsonResponse(await slow.promise);
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMetaSources("/lib/a.mp3", "", { enabled: true }));
    expect(result.current.records).toBeNull();

    await waitFor(() => expect(result.current.records).toEqual([ITUNES]));
    expect(result.current.pending).toEqual(["discogs"]);
    expect(result.current.order).toEqual(["itunes", "discogs"]);

    await act(async () => {
      slow.resolve({ records: [DISCOGS] });
    });
    await waitFor(() => expect(result.current.records).toEqual([ITUNES, DISCOGS]));
    expect(result.current.pending).toEqual([]);
    expect(fetchMock.mock.calls.filter(([u]) => u === "/api/fetch/meta")).toHaveLength(2);
  });

  it("все источники упали → «Источники недоступны»", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse(SETTINGS);
        return jsonResponse({ detail: "network" }, 502);
      }),
    );
    const { result } = renderHook(() => useMetaSources("/lib/a.mp3", "", { enabled: true }));
    await waitFor(() => expect(result.current.records).toEqual([]));
    expect(result.current.pending).toEqual([]);
    expect(toast).toHaveBeenCalledWith({ code: "editor.sources_unavailable" }, "warn");
  });

  it("настройки недоступны — одним общим запросом без sources", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/settings") return jsonResponse({ detail: "oops" }, 500);
      if (url === "/api/fetch/meta") {
        expect(postBody(init).sources).toBeUndefined();
        return jsonResponse({ records: [ITUNES, DISCOGS] });
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMetaSources("/lib/a.mp3", "http://t/1.jpg", { enabled: true }));
    await waitFor(() => expect(result.current.records).toEqual([ITUNES, DISCOGS]));
    expect(result.current.pending).toEqual([]);
    expect(postBody(fetchMock.mock.calls.find(([u]) => u === "/api/fetch/meta")?.[1]).thumbnail_url).toBe(
      "http://t/1.jpg",
    );
  });

  it("пустой список источников в настройках — записей нет", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/settings") return jsonResponse({ metadata_sources: [], metadata_sources_available: [] });
        throw new Error(`unexpected ${url}`);
      }),
    );
    const { result } = renderHook(() => useMetaSources("/lib/a.mp3", "", { enabled: true }));
    await waitFor(() => expect(result.current.records).toEqual([]));
    expect(toast).not.toHaveBeenCalled();
  });

  it("по-источниковый кэш: повторное открытие не бьёт по сети", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/settings") return jsonResponse(SETTINGS);
      const src = postBody(init).sources?.[0];
      return jsonResponse({ records: src === "itunes" ? [ITUNES] : [DISCOGS] });
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = renderHook(() => useMetaSources("/lib/a.mp3", "", { enabled: true }));
    await waitFor(() => expect(first.result.current.records).toEqual([ITUNES, DISCOGS]));
    first.unmount();

    const second = renderHook(() => useMetaSources("/lib/a.mp3", "", { enabled: true }));
    await waitFor(() => expect(second.result.current.records).toEqual([ITUNES, DISCOGS]));
    second.unmount();

    const metaCalls = fetchMock.mock.calls.filter(([u]) => u === "/api/fetch/meta");
    expect(metaCalls).toHaveLength(2); // по одному на источник за всё время
  });

  it("metaPromise: все источники одним ответом", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useMetaSources("/lib/a.mp3", "", { enabled: true, metaPromise: Promise.resolve({ records: [ITUNES] }) }),
    );
    await waitFor(() => expect(result.current.records).toEqual([ITUNES]));
    expect(result.current.pending).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled(); // сеть не трогаем — промис готов
  });

  it("metaPromise отклонён → записи пусты + warn", async () => {
    vi.stubGlobal("fetch", vi.fn());
    // Побочный catch подавляет unhandled-rejection, хук всё равно получит reject.
    const failed = Promise.reject(new Error("offline"));
    failed.catch(() => {});
    const { result } = renderHook(() =>
      useMetaSources("/lib/a.mp3", "", { enabled: true, metaPromise: failed }),
    );
    await waitFor(() => expect(result.current.records).toEqual([]));
    expect(toast).toHaveBeenCalledWith({ code: "editor.sources_unavailable_reason", params: { reason: "offline" } }, "warn");
  });

  it("сохраняет descriptor ApiError в reason уведомления", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const failed = Promise.reject(new ApiError({ code: "jobs.common.failed", message: "Error" }));
    failed.catch(() => {});
    const { result } = renderHook(() =>
      useMetaSources("/lib/a.mp3", "", { enabled: true, metaPromise: failed }),
    );

    await waitFor(() => expect(result.current.records).toEqual([]));
    expect(toast).toHaveBeenCalledWith(
      { code: "editor.sources_unavailable_reason", params: { reason: { code: "jobs.common.failed", message: "Error" } } },
      "warn",
    );
  });

  it("enabled=false — запросов нет", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useMetaSources("/lib/a.mp3", "", { enabled: false }));
    expect(result.current.records).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
