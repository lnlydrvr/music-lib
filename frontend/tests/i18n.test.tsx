import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  bootstrapLanguage,
  changeLanguage,
  getProvisionalLanguage,
  default as i18n,
  resolveLanguage,
  resolveMessage,
  removePending,
} from "../src/i18n";
import { asRenderableMessage } from "../src/i18n/messages";
import { ApiError } from "../src/lib/api";
import { ProgressBar } from "../src/components/ui/ProgressBar";
import { Pipeline } from "../src/components/ui/Pipeline";
import { Spinner } from "../src/components/ui/Spinner";
import { PlayerBar } from "../src/components/PlayerBar";
import { QueueItem } from "../src/components/ui/QueueItem";
import { TrackRow } from "../src/components/ui/TrackRow";
import { AlbumDetail } from "../src/features/ytm/detail";
import App from "../src/App";
import { AppToaster, toast } from "../src/lib/toast";
import { usePlayer } from "../src/stores/player";
import { useDownloads } from "../src/stores/downloads";
import { DownloadsDock } from "../src/components/DownloadsDock";
import { act, render, screen } from "@testing-library/react";
import en from "../src/locales/en.json";
import ru from "../src/locales/ru.json";

function leaves(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object") return [prefix];
  return Object.entries(value).flatMap(([key, child]) => leaves(child, prefix ? `${prefix}.${key}` : key));
}

function icuParams(value: unknown): string[] {
  if (typeof value !== "string") return [];
  return [...value.matchAll(/\{([a-zA-Z][\w]*)\s*,\s*(?:plural|select|selectordinal)/g)].map((m) => m[1])
    .concat([...value.matchAll(/\{([a-zA-Z][\w]*)\}/g)].map((m) => m[1]))
    .filter((name, index, all) => all.indexOf(name) === index).sort();
}


describe("i18n runtime", () => {
  beforeEach(() => {
    usePlayer.setState({ src: "", title: "", artist: "", coverUrl: "", visible: false, seq: 0 });
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("resolves saved and browser locales, including regional tags", () => {
    expect(resolveLanguage("ru", "en-GB")).toBe("ru");
    expect(resolveLanguage(null, "ru-RU")).toBe("ru");
    expect(resolveLanguage(null, "en-GB")).toBe("en");
    expect(resolveLanguage(null, "de-DE")).toBe("en");
  });

  it("uses local storage only until an unset server setting resolves to the browser locale", async () => {
    localStorage.setItem("music-lib-language", "ru");
    expect(getProvisionalLanguage("en-GB")).toBe("ru");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ language: null }) }));

    await bootstrapLanguage("en-GB");

    expect(document.documentElement.lang).toBe("en");
  });

  it("lets the persisted server selection override a provisional locale", async () => {
    localStorage.setItem("music-lib-language", "en");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ language: "ru" }) }));

    await bootstrapLanguage("en-GB");

    expect(document.documentElement.lang).toBe("ru");
    expect(localStorage.getItem("music-lib-language")).toBe("ru");
  });

  it("preserves the provisional locale when the settings response is unsuccessful", async () => {
    await changeLanguage("ru");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await bootstrapLanguage("en-GB");

    expect(document.documentElement.lang).toBe("ru");
    expect(localStorage.getItem("music-lib-language")).toBe("ru");
  });

  it("normalizes an unsupported active i18n language after a bootstrap failure", async () => {
    await i18n.changeLanguage("de-DE");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(bootstrapLanguage("en-GB")).resolves.toBe("en");
  });

  it("abandons an unresolved settings request and preserves the provisional locale", async () => {
    vi.useFakeTimers();
    await changeLanguage("ru");
    let aborted = false;
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise((_, reject) => {
      init?.signal?.addEventListener("abort", () => {
        aborted = true;
        reject(new DOMException("Request aborted", "AbortError"));
      });
    })));

    const bootstrap = bootstrapLanguage("en-GB");
    await vi.advanceTimersByTimeAsync(5_000);

    expect(aborted).toBe(true);
    await expect(bootstrap).resolves.toBe("ru");
    expect(document.documentElement.lang).toBe("ru");
  });

  it("clears the bootstrap timeout after settings load successfully", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ language: "en" }) }));

    await bootstrapLanguage("ru-RU");

    expect(vi.getTimerCount()).toBe(0);
  });

  it("tolerates denied local storage", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });

    expect(getProvisionalLanguage("ru-RU")).toBe("ru");
    await act(async () => { await changeLanguage("en"); });
    expect(document.documentElement.lang).toBe("en");

    getItem.mockRestore();
    setItem.mockRestore();
  });

  it("renders legacy strings, known descriptors, and safe unknown fallbacks", async () => {
    await changeLanguage("ru");

    expect(resolveMessage("Старое сообщение")).toBe("Старое сообщение");
    expect(resolveMessage({ code: "settings.language.save_failed" })).toBe("Язык изменён, но сохранить выбор не удалось");
    expect(resolveMessage({ code: "api.errors.unknown", message: "Readable fallback" })).toBe("Readable fallback");
    expect(resolveMessage({ code: "api.errors.unknown" })).toBe("Что-то пошло не так");
  });

  it("renders a descriptor with the caller translation scope instead of the global singleton", async () => {
    await changeLanguage("ru");

    expect(resolveMessage({ code: "settings.language.save_failed" }, i18n.getFixedT("en"))).toBe(
      "Language changed, but could not be saved",
    );
  });

  it("rerenders an open structured toast in the active translation scope", async () => {
    await changeLanguage("ru");
    render(<AppToaster />);
    toast({ code: "settings.language.save_failed" });
    expect(await screen.findByText("Язык изменён, но сохранить выбор не удалось")).toBeInTheDocument();

    await changeLanguage("en");

    expect(await screen.findByText("Language changed, but could not be saved")).toBeInTheDocument();
  });

  it("keeps an ApiError descriptor localizable after the locale changes", async () => {
    const error = new ApiError({ code: "api.fields.integer_required", message: "Must be an integer" });

    await changeLanguage("en");
    expect(asRenderableMessage(error)).toEqual({ code: "api.fields.integer_required", message: "Must be an integer" });
    expect(resolveMessage(asRenderableMessage(error))).toBe("Must be an integer");

    await changeLanguage("ru");
    expect(resolveMessage(asRenderableMessage(error))).toBe("Должно быть целым числом");
  });

  it("uses catalog resources directly at runtime", async () => {
    await changeLanguage("ru");

    expect(i18n.t("library.track.compression_label")).toBe("Сжатие");
  });

  it("removes pending nested keys without mutating the source catalog", () => {
    const source = { section: { translated: "Sí", pending: "English" } };

    expect(removePending(source, ["section.pending"])).toEqual({ section: { translated: "Sí" } });
    expect(source).toEqual({ section: { translated: "Sí", pending: "English" } });
  });

  it("localizes the mounted App skip link from the shell catalog", async () => {
    window.location.hash = "#library";
    await changeLanguage("ru");
    render(<App />);

    const skipLink = screen.getByRole("link", { name: "Перейти к содержимому" });
    await changeLanguage("en");

    expect(skipLink).toHaveAccessibleName("Skip to content");
  });

  it("provides a shared empty-state message for YTM consumers", async () => {
    await changeLanguage("en");
    expect(i18n.t("ytm.empty")).toBe("Nothing found");

    await changeLanguage("ru");
    expect(i18n.t("ytm.empty")).toBe("Ничего не найдено");
    expect(en.ytm.empty).toBeDefined();
    expect(ru.ytm.empty).toBeDefined();
  });

  it("resolves Lucida-specific readiness and failure keys in both locales", async () => {
    await changeLanguage("en");
    expect(i18n.t("lucida.chromium_required")).toBe("Chromium is required for Lucida.");
    expect(i18n.t("api.errors.lucida_failed")).toBe("Lucida request failed.");

    await changeLanguage("ru");
    expect(i18n.t("lucida.chromium_required")).toBe("Для Lucida требуется Chromium.");
    expect(i18n.t("api.errors.lucida_failed")).toBe("Запрос к Lucida не выполнен.");
  });

  it("localizes the ProgressBar accessible name in Russian and English", async () => {
    render(<ProgressBar pct={25} />);
    const progress = await screen.findByRole("progressbar", { name: "Ход выполнения операции" });
    expect(progress).toHaveAttribute("aria-valuenow", "25");

    await changeLanguage("en");

    await screen.findByRole("progressbar", { name: "Operation progress" });
    expect(progress).toHaveAccessibleName("Operation progress");
    expect(progress).toHaveAttribute("aria-valuenow", "25");
  });

  it("rerenders mounted queue descriptors and the empty track value after locale changes", async () => {
    await changeLanguage("ru");
    render(
      <>
        <QueueItem entry={{ id: 1, title: { code: "jobs.download.name" }, sub: { code: "queue.done" }, pct: 100, state: "done" }} />
        <TrackRow />
      </>,
    );
    expect(screen.getByText("Скачивание")).toBeInTheDocument();
    expect(screen.getByText("Готово")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();

    await changeLanguage("en");

    expect(screen.getByText("Download")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("rerenders an active Shazam job message after a locale switch", async () => {
    await changeLanguage("ru");
    useDownloads.setState({
      expanded: true,
      items: {
        shazam: {
          id: "shazam",
          title: { code: "jobs.shazam.scan_name", message: "Shazam — search" },
          name: { code: "jobs.shazam.scan_name", message: "Shazam — search" },
          status: "active",
          percent: 25,
          msg: { code: "jobs.shazam.scanning", params: { count: 2 }, message: "Searching for 2 tracks in YouTube Music…" },
          addedAt: Date.now(),
        },
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<DownloadsDock />);

    expect(screen.getByText("Shazam — поиск")).toBeInTheDocument();
    expect(screen.getByText("Поиск 2 треков в YouTube Music…")).toBeInTheDocument();

    await changeLanguage("en");

    expect(screen.getByText("Shazam — search")).toBeInTheDocument();
    expect(screen.getByText("Searching for 2 tracks in YouTube Music…")).toBeInTheDocument();
  });

  it("rerenders mounted loading, pipeline, player, and descriptor error UI after locale changes", async () => {
    await changeLanguage("ru");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ detail: { code: "api.fields.integer_required", message: "Must be an integer" } }),
      headers: { get: () => "application/json" },
    }));
    usePlayer.getState().play({ src: "/preview" });
    render(
      <>
        <Spinner />
        <Pipeline
          visible
          stages={[
            { id: "expected", label: "Expected" },
            { id: "running", label: { code: "jobs.download.name" } },
            { id: "done", label: "Done" },
            { id: "error", label: "Error" },
            { id: "skipped", label: "Skipped" },
          ]}
          states={["pending", "active", "done", "error", "skip"]}
        />
        <PlayerBar />
        <AlbumDetail id="broken" />
      </>,
    );

    expect(await screen.findByText("Загрузка…")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Этапы операции" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Expected: ожидает" })).toHaveAttribute("data-id", "expected");
    expect(screen.getByRole("listitem", { name: "Скачивание: выполняется" })).toHaveAttribute("data-state", "active");
    expect(screen.getByRole("listitem", { name: "Done: готово" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Error: ошибка" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Skipped: пропущен" })).toBeInTheDocument();
    expect(screen.getByText("Превью")).toBeInTheDocument();
    expect(await screen.findByText("Должно быть целым числом")).toBeInTheDocument();

    await changeLanguage("en");

    expect(await screen.findByText("Loading…")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Operation stages" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Expected: expected" })).toHaveAttribute("data-id", "expected");
    expect(screen.getByRole("listitem", { name: "Download: running" })).toHaveAttribute("data-state", "active");
    expect(screen.getByRole("listitem", { name: "Done: done" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Error: error" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Skipped: skipped" })).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(await screen.findByText("Must be an integer")).toBeInTheDocument();
  });

  it("includes track and tracks in ICU argument validation", () => {
    expect(icuParams("{track} {tracks}")).toEqual(["track", "tracks"]);
  });

  it("keeps complete English and Russian catalog trees and ICU parameters in parity", () => {
    expect(leaves(en).sort()).toEqual(leaves(ru).sort());
    const params = (value: any, prefix = ""): Record<string, string[]> => {
      if (typeof value === "string") return { [prefix]: icuParams(value) };
      return Object.entries(value || {}).reduce((out, [key, child]) => ({ ...out, ...params(child, prefix ? `${prefix}.${key}` : key) }), {});
    };
    expect(params(ru)).toEqual(params(en));
  });
});
