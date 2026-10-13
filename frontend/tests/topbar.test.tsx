import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Topbar } from "../src/components/Topbar";
import { ROUTE_IMPORTS } from "../src/lib/prefetch";
import { changeLanguage } from "../src/i18n";

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, statusText: "", json: async () => body, headers: { get: () => "application/json" } };
}

function stubFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      for (const [key, body] of Object.entries(routes)) {
        if (url.includes(key)) return jsonResponse(body);
      }
      return jsonResponse({}, 404);
    }),
  );
}

beforeEach(() => {
  vi.stubGlobal("setInterval", vi.fn(() => 0));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/* NumberFlow: в jsdom цифры дублируются в light DOM (declarative shadow
   template остаётся шаблоном) рядом со служебным <style> — собираем текст
   дерева, пропуская style/script/template. */
function deepText(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent || "";
  const el = node as Element;
  if (/^(STYLE|SCRIPT|TEMPLATE)$/.test(el.tagName)) return "";
  if (el.shadowRoot) return deepText(el.shadowRoot);
  let out = "";
  node.childNodes.forEach((c) => {
    out += deepText(c);
  });
  return out;
}

const statsText = () => deepText(document.getElementById("sidebar-stats")!);

describe("Topbar · статистика библиотеки", () => {
  it("обновляет статистику каждые 30 секунд", () => {
    stubFetch({
      "/api/state": { tracks: 10, size_mb: 2 },
      "/api/library/quality": { total: 10, tracks: [] },
    });
    render(<Topbar route="menu" theme="dark" onToggleTheme={() => {}} />);
    expect(setInterval).toHaveBeenCalledWith(expect.any(Function), 30_000);
  });

  it("процент здоровья + треки · размер, зелёный при 100%", async () => {
    stubFetch({
      "/api/state": { tracks: 10, size_mb: 2 },
      "/api/library/quality": { total: 10, tracks: [] },
    });
    render(<Topbar route="menu" theme="dark" onToggleTheme={() => {}} />);
    await waitFor(() => expect(statsText()).toBe("[100%] 10 треков · 2,0 МБ"));
    const health = document.querySelector<HTMLElement>(".stats-health")!;
    expect(deepText(health)).toBe("[100%] ");
    expect(health).toHaveStyle({ color: "var(--ok)" });
  });

  it("90% — жёлтый (warn), проблема в отчёте уменьшает процент", async () => {
    stubFetch({
      "/api/state": { tracks: 10, size_mb: 2 },
      "/api/library/quality": { total: 10, tracks: [{ path: "/x" }] },
    });
    render(<Topbar route="menu" theme="dark" onToggleTheme={() => {}} />);
    const health = await waitFor(() => {
      const el = document.querySelector<HTMLElement>(".stats-health");
      expect(el).toBeTruthy();
      expect(deepText(el!)).toBe("[90%] ");
      return el!;
    });
    expect(health).toHaveStyle({ color: "var(--warn)" });
  });

  it("отчёт качества недоступен — статистика без процента", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/api/state")) return jsonResponse({ tracks: 7, size_mb: 1 });
        throw new Error("boom");
      }),
    );
    render(<Topbar route="menu" theme="dark" onToggleTheme={() => {}} />);
    await waitFor(() => expect(statsText()).toBe("7 треков · 1,0 МБ"));
    expect(document.querySelector(".stats-health")).toBeNull();
  });
});

describe("Topbar · префетч маршрутов", () => {
  it("hover и фокус ссылки навигации греют чанк экрана (идемпотентно)", async () => {
    stubFetch({
      "/api/state": { tracks: 1, size_mb: 1 },
      "/api/library/quality": { total: 1, tracks: [] },
    });
    const load = vi.fn(() => Promise.resolve({ default: () => null }));
    vi.spyOn(ROUTE_IMPORTS, "library").mockImplementation(load);

    render(<Topbar route="menu" theme="dark" onToggleTheme={() => {}} />);
    const link = screen.getByRole("link", { name: /Библиотека/ });
    fireEvent.pointerEnter(link);
    fireEvent.focus(link);

    // оба события прошли через guard — импортер вызван один раз
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
  });
});

describe("Topbar · locale", () => {
  it("переводит навигацию после смены языка без перемонтирования", async () => {
    stubFetch({ "/api/state": { tracks: 0, size_mb: 0 }, "/api/library/quality": { total: 0, tracks: [] } });
    render(<Topbar route="menu" theme="dark" onToggleTheme={() => {}} />);

    await changeLanguage("en");
    expect(screen.getByRole("link", { name: /Library/ })).toBeInTheDocument();
    await changeLanguage("ru");
    expect(screen.getByRole("link", { name: /Библиотека/ })).toBeInTheDocument();
  });
});
