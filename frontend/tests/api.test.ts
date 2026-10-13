import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, coverUrl, get, post } from "../src/lib/api";

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status < 400,
    status,
    statusText: "Err",
    json: async () => body,
    headers: { get: () => "application/json" },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api", () => {
  it("успешный JSON-ответ разбирается", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ hello: "world" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(get("/api/x")).resolves.toEqual({ hello: "world" });
  });

  it("GET-параметры попадают в query", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    await get("/api/jobs", { limit: 10 });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toBe("/api/jobs?limit=10");
  });

  it("сохраняет строковый detail как legacy renderable message и статус", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Путь не найден" }, 404)));
    const err = await get("/api/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("Путь не найден");
    expect(err.status).toBe(404);
    expect(err.renderableMessage).toBe("Путь не найден");
    expect(err.fields).toBeNull();
  });

  it("detail {message} → message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: { message: "Внутри детали" } }, 400)));
    const err = await get("/api/x").catch((e) => e);
    expect(err.message).toBe("Внутри детали");
    expect(err.renderableMessage).toBe("Внутри детали");
  });

  it("сохраняет структурированные detail и field errors без раннего рендеринга", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({
        detail: { code: "api.errors.check_fields", params: {}, message: "Check the fields" },
        errors: {
          year: { code: "api.fields.year_four_digits", params: {}, message: "Year must be four digits, e.g. 2024" },
        },
      }, 422)),
    );
    const err = await post("/api/tags/apply", {}).catch((e) => e);
    expect(err.status).toBe(422);
    expect(err.message).toBe("Check the fields");
    expect(err.renderableMessage).toEqual({ code: "api.errors.check_fields", params: {}, message: "Check the fields" });
    expect(err.fields).toEqual({
      year: { code: "api.fields.year_four_digits", params: {}, message: "Year must be four digits, e.g. 2024" },
    });
  });

  it("сохраняет legacy string field errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Check fields", errors: { year: "Must be an integer" } }, 422)));
    const err = await post("/api/tags/apply", {}).catch((e) => e);
    expect(err.fields).toEqual({ year: "Must be an integer" });
  });

  it("использует fallback неизвестного кода в Error.message, сохраняя дескриптор", async () => {
    const detail = { code: "provider.errors.unknown", params: { provider: "X" }, message: "Provider failed" };
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail }, 502)));
    const err = await get("/api/x").catch((e) => e);
    expect(err.renderableMessage).toEqual(detail);
    expect(err.message).toBe("Provider failed");
  });

  it("нечитаемое тело → статус и renderableMessage", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new Error("not json");
      },
      headers: { get: () => "text/html" },
    })));
    const err = await get("/api/x").catch((e) => e);
    expect(err.status).toBe(502);
    expect(err.message).toBe("502 Bad Gateway");
    expect(err.renderableMessage).toBe("502 Bad Gateway");
  });

  it("coverUrl кодирует путь", () => {
    expect(coverUrl("/Music/А й Б.mp3")).toBe(`/api/cover?path=${encodeURIComponent("/Music/А й Б.mp3")}`);
  });
});
