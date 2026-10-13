import { describe, expect, it, vi } from "vitest";
import { ROUTES } from "../src/routes";

/* Guard префетча живёт в состоянии модуля — каждый тест берёт свежую копию. */
async function fresh() {
  vi.resetModules();
  return await import("../src/lib/prefetch");
}

/* Стаб модуля экрана: без загрузки реальных чанков. */
const stubModule = () => Promise.resolve({ default: () => null });

describe("prefetchRoute", () => {
  it("вызывает импортер маршрута; повторные вызовы не дублируют запрос", async () => {
    const { ROUTE_IMPORTS, prefetchRoute } = await fresh();
    const load = vi.fn(stubModule);
    vi.spyOn(ROUTE_IMPORTS, "settings").mockImplementation(load);

    prefetchRoute("settings");
    prefetchRoute("settings");
    prefetchRoute("settings");

    expect(load).toHaveBeenCalledTimes(1);
  });

  it("глотает reject импорта и позволяет повторить попытку", async () => {
    const { ROUTE_IMPORTS, prefetchRoute } = await fresh();
    const load = vi.fn(() => Promise.reject(new Error("network")));
    vi.spyOn(ROUTE_IMPORTS, "discover").mockImplementation(load);

    expect(() => prefetchRoute("discover")).not.toThrow();
    // catch внутри prefetchRoute выполняется микрозадачей — даём ей отработать
    await new Promise((r) => setTimeout(r, 0));

    // guard снят после неудачи — следующий hover повторит запрос
    prefetchRoute("discover");
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("карта импортеров покрывает все маршруты и открывает реальные экраны", async () => {
    const { ROUTE_IMPORTS } = await fresh();
    expect(Object.keys(ROUTE_IMPORTS).sort()).toEqual([...ROUTES].sort());
    for (const route of ROUTES) {
      const mod = await ROUTE_IMPORTS[route]();
      expect(typeof mod.default, `экран ${route}`).toBe("function");
    }
  });
});
