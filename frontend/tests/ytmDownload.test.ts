import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { ApiError } from "../src/lib/api";
import { changeLanguage } from "../src/i18n";

const { startJob, toast } = vi.hoisted(() => ({
  startJob: vi.fn(),
  toast: vi.fn(),
}));

vi.mock("../src/lib/jobs", () => ({ startJob }));
vi.mock("../src/lib/toast", () => ({ toast }));
vi.mock("../src/features/ytm/settings", () => ({
  ytmSettings: vi.fn(async () => ({})),
  fmtSetting: vi.fn((_settings, _key, fallback) => fallback),
}));

import { downloadAllLabel, ytmDownload } from "../src/features/ytm/download";
import { DownloadAllButton } from "../src/features/ytm/detail";

describe("ytmDownload", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("constructs the archive name only from the target kind and immutable provider ID", async () => {
    startJob.mockResolvedValueOnce({ archive: "/library/Playlists/Album A.m3u8", ok: 2 });

    await ytmDownload([{ video_id: "video", title: "Track" }], {
      kind: "album",
      providerId: "MPREb_012345",
      title: { code: "ytm.download.album_name", params: { title: "Album A" } },
    });

    expect(startJob).toHaveBeenCalledWith(
      "/api/ytmusic/download",
      expect.objectContaining({ playlist: "ytm-album-MPREb_012345" }),
      expect.objectContaining({ title: { code: "ytm.download.album_name", params: { title: "Album A" } } }),
    );
  });

  it("never derives the filesystem archive name from a localized title containing a slash", async () => {
    startJob.mockResolvedValueOnce({ archive: "/library/Playlists/Album A.m3u8", ok: 1 });
    await changeLanguage("ru");

    await ytmDownload([{ video_id: "video", title: "Track" }], {
      kind: "album",
      providerId: "MPREb_012345",
      title: { code: "ytm.download.album_name", params: { title: "Альбом / Album" } },
    });

    expect(startJob).toHaveBeenCalledWith(
      "/api/ytmusic/download",
      expect.objectContaining({ playlist: "ytm-album-MPREb_012345" }),
      expect.objectContaining({ title: { code: "ytm.download.album_name", params: { title: "Альбом / Album" } } }),
    );
  });

  it("URL-encodes an adversarial provider ID before putting it in the archive request", async () => {
    startJob.mockResolvedValueOnce({ archive: "/library/Playlists/Album A.m3u8", ok: 1 });

    await ytmDownload([{ video_id: "video", title: "Track" }], {
      kind: "album",
      providerId: "../a/b",
      title: { code: "ytm.download.album_name", params: { title: "Album A" } },
    });

    expect(startJob).toHaveBeenCalledWith(
      "/api/ytmusic/download",
      expect.objectContaining({ playlist: "ytm-album-..%2Fa%2Fb" }),
      expect.anything(),
    );
  });

  it.each([
    ["en", 1, "1 track"],
    ["en", 2, "2 tracks"],
    ["ru", 1, "1 трек"],
    ["ru", 2, "2 трека"],
    ["ru", 5, "5 треков"],
  ] as const)("formats track counts with ICU pluralization in %s for %i", async (locale, count, expected) => {
    await changeLanguage(locale);

    expect((await import("../src/i18n")).default.t("ytm.tracks.count", { count })).toBe(expected);
  });

  it("renders its completion message and batch label from the active catalog", async () => {
    startJob.mockResolvedValueOnce({ archive: "/library/Playlists/Mix.m3u8", ok: 1 });
    await changeLanguage("en");

    await ytmDownload([{ video_id: "video", title: "Track" }], {
      kind: "playlist",
      providerId: "mix",
      title: { code: "ytm.download.playlist_name", params: { title: "Mix" } },
    });

    expect(toast).toHaveBeenCalledWith("Archive: Mix.m3u8");
    expect(downloadAllLabel(2)).toBe("Download missing (2)");
    expect(downloadAllLabel(0)).toBe("Everything is already in the library");

    startJob.mockResolvedValueOnce({ ok: 2 });
    await changeLanguage("ru");

    await ytmDownload([{ video_id: "video", title: "Track" }], {
      kind: "playlist",
      providerId: "mix",
      title: { code: "ytm.download.playlist_name", params: { title: "Mix" } },
    });

    expect(toast).toHaveBeenLastCalledWith("Скачано: 2");
    expect(downloadAllLabel(2)).toBe("Скачать отсутствующие (2)");
    expect(downloadAllLabel(0)).toBe("Всё уже в библиотеке");
  });

  it.each([
    ["en", "Download popular (1)"],
    ["ru", "Скачать популярные (1)"],
  ] as const)("downloads only missing popular tracks through the target contract in %s", async (locale, label) => {
    await changeLanguage(locale);
    const user = userEvent.setup();
    const onDownload = vi.fn();
    const target = {
      kind: "artist" as const,
      providerId: "UC123",
      title: { code: "ytm.download.artist_name" as const, params: { title: "Artist" } },
    };
    const missing = { video_id: "one", title: "Missing" };
    render(createElement(DownloadAllButton, {
      items: [missing, { video_id: "two", title: "Saved", in_library: true }],
      target,
      onDownload,
      labelKey: "ytm.download.popular",
    }));

    await user.click(screen.getByRole("button", { name: label }));

    expect(onDownload).toHaveBeenCalledWith([missing], target);
  });

  it("retains structured API errors for localization at the toast boundary", async () => {
    startJob.mockRejectedValueOnce(new ApiError({ code: "api.fields.integer_required", message: "Must be an integer" }));

    await ytmDownload([{ video_id: "video", title: "Track" }], {
      kind: "track",
      providerId: "video",
      title: { code: "jobs.ytm.name" },
    });

    expect(toast).toHaveBeenCalledWith({ code: "api.fields.integer_required", message: "Must be an integer" }, "error");
  });
});
