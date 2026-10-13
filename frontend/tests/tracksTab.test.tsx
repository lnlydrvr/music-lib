import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TracksTab } from "../src/views/library/TracksTab";
import type { YTMTrack } from "../src/features/ytm";
import type { TrackRow } from "../src/views/library/libUtils";
import type { YtApi } from "../src/views/library/useYtData";
import type { TrackDetailActions } from "../src/views/library/trackDetail";
import { changeLanguage } from "../src/i18n";

function track(path: string, title: string, artist: string): TrackRow {
  return {
    path, title, artist, album: "", year: "", genre: "", album_artist: "", isrc: "", composer: "",
    track_number: "", disc_number: "", size_bytes: 0, duration_seconds: 0, bitrate: 0, mtime: 0,
    has_lyrics: false, has_synced_lyrics: false, has_cover: false, ext: ".mp3",
  };
}

const ACTIONS: TrackDetailActions = {
  editTags: vi.fn(),
  metaflow: vi.fn(),
  viewLyrics: vi.fn(),
  compress: vi.fn(),
  deleteTrack: vi.fn(),
};

function renderTracks(rows: TrackRow[], liked: YTMTrack[], lib: YTMTrack[], opts: { detailPath?: string; onDetail?: (p: string) => void } = {}) {
  const yt = {
    ytData: vi.fn(async (kind: string) => (kind === "liked" ? liked : kind === "library_songs" ? lib : [])),
    findAlbumTwin: vi.fn(async () => null),
    ytArtistAlbums: vi.fn(async () => []),
    refreshAfterYtDownload: vi.fn(async () => {}),
    connected: null,
    epoch: 0,
  } as unknown as YtApi;
  return render(
    <TracksTab
      items={rows}
      list={rows}
      sort="path"
      density="full"
      query=""
      selected={new Set()}
      toggleSelect={() => {}}
      detailPath={opts.detailPath || ""}
      onDetail={opts.onDetail || (() => {})}
      yt={yt}
      actions={ACTIONS}
      onCount={() => {}}
    />,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TracksTab: дедуп и бейджи", () => {
  const local1 = track("/lib/one.mp3", "Song One", "Artist X");
  const local2 = track("/lib/two.mp3", "Song Two", "Artist Z");
  const rows = [local1, local2];

  it("дедуп по video_id: лайк+библиотека — одна карточка; in_library скрыт", async () => {
    const liked: YTMTrack[] = [
      { video_id: "v1", title: "Song One", artist: "Artist X" }, // дублируется в library_songs
      { video_id: "v2", title: "Cloud Song", artist: "Artist Y" },
    ];
    const lib: YTMTrack[] = [
      { video_id: "v1", title: "Song One", artist: "Artist X" },
      { video_id: "v3", title: "Hidden", artist: "A", in_library: true }, // уже в файлах — скрыт
    ];
    renderTracks(rows, liked, lib);

    // YT-карточки: v1 и v2 (v3 скрыт, v1 не дублируется).
    await waitFor(() => expect(screen.getAllByLabelText(/YouTube Music:/)).toHaveLength(2));
    // «Радио» только у YT-карточек (локальные карточки его не имеют).
    expect(screen.getAllByRole("button", { name: /Похожие: / })).toHaveLength(2);
    // Локальный трек с ключом лайка — бейдж «♥ YT».
    const localCard = document.querySelector('.lib-card[data-path="/lib/one.mp3"]')!;
    expect(localCard.querySelector(".lib-yt-badge")!.textContent).toBe("♥ YT");
    const local2Card = document.querySelector('.lib-card[data-path="/lib/two.mp3"]')!;
    expect(local2Card.querySelector(".lib-yt-badge")).toBeNull();
    // Лайкнутые YT-карточки — с «♥» (по одной на карточку).
    expect(document.querySelectorAll('.lib-card.yt [title="Лайк в YouTube Music"]').length).toBe(2);
  });

  it("клик по локальной карточке открывает панель «Информация» с деталями", async () => {
    const user = userEvent.setup();
    const onDetail = vi.fn();
    renderTracks(rows, [], [], { onDetail });
    await user.click(screen.getByRole("button", { name: /Открыть детали: Song One — Artist X/ }));
    expect(onDetail).toHaveBeenCalledWith("/lib/one.mp3");
  });

  it("detailPath подсвечивает активную карточку и заполняет панель", async () => {
    renderTracks(rows, [], [], { detailPath: "/lib/two.mp3" });
    await waitFor(() => {
      const active = document.querySelector('.lib-card[data-path="/lib/two.mp3"]');
      expect(active?.className).toContain("active");
    });
    expect(screen.getByText("Информация")).toBeInTheDocument();
    expect(screen.getByText("Название:")).toBeInTheDocument();
    expect(screen.getAllByText("Song Two").length).toBe(2); // карточка + панель
    expect(screen.getByRole("button", { name: "Редактировать теги" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Удалить трек" })).toBeInTheDocument();
  });
});

/* Первичная сортировка «По пути»: до ответа YT Music — порядок API как есть
   (бэкенд уже отсортировал; для путей это кодепоинтный порядок), локальная
   localeCmp-пересортировка — только после ответа (как фазы renderTrackGrid
   в library.js). Числа в путях выбраны так, чтобы порядки отличались
   независимо от локали: кодепоинт «Track 10» < «Track 2», numeric-коллация — наоборот. */
describe("TracksTab: первичный порядок «По пути»", () => {
  const t10 = track("/lib/A/Track 10.mp3", "Track Ten", "Artist A");
  const t2 = track("/lib/A/Track 2.mp3", "Track Two", "Artist A");
  const apiOrder = [t10, t2]; // как отдаёт GET /api/library?sort=path

  function renderWithDeferredYt() {
    let resolveYt: (v: never[]) => void = () => {};
    const ytPromise = new Promise<never[]>((r) => { resolveYt = r; });
    const yt = {
      ytData: vi.fn(async (kind: string) =>
        kind === "liked" || kind === "library_songs" ? ytPromise : ([] as never[])),
      findAlbumTwin: vi.fn(async () => null),
      ytArtistAlbums: vi.fn(async () => []),
      refreshAfterYtDownload: vi.fn(async () => {}),
      connected: null,
      epoch: 0,
    } as unknown as YtApi;
    render(
      <TracksTab
        items={apiOrder}
        list={apiOrder}
        sort="path"
        density="full"
        query=""
        selected={new Set()}
        toggleSelect={() => {}}
        detailPath=""
        onDetail={() => {}}
        yt={yt}
        actions={ACTIONS}
        onCount={() => {}}
      />,
    );
    return { resolveYt: () => resolveYt([]) };
  }

  const cardPaths = () =>
    [...document.querySelectorAll(".lib-grid .lib-card")].map((c) => (c as HTMLElement).dataset.path);

  it("до ответа YT — порядок API без локальной пересортировки", () => {
    renderWithDeferredYt();
    expect(cardPaths()).toEqual(["/lib/A/Track 10.mp3", "/lib/A/Track 2.mp3"]);
  });

  it("после ответа YT (пусть пустого) — общий localeCmp-порядок", async () => {
    const h = renderWithDeferredYt();
    expect(cardPaths()[0]).toBe("/lib/A/Track 10.mp3");
    h.resolveYt();
    await waitFor(() => expect(cardPaths()[0]).toBe("/lib/A/Track 2.mp3"));
    expect(cardPaths()).toEqual(["/lib/A/Track 2.mp3", "/lib/A/Track 10.mp3"]);
  });
});

describe("TracksTab: locale-aware ordering", () => {
  const latin = track("/lib/latin.mp3", "Бета", "Artist");
  const cyrillic = track("/lib/cyrillic.mp3", "Alpha", "Artist");
  const cardPaths = () =>
    [...document.querySelectorAll(".lib-grid .lib-card")].map((card) => (card as HTMLElement).dataset.path);

  it("re-sorts Latin and Cyrillic titles after the active locale changes", async () => {
    await changeLanguage("en");
    render(
      <TracksTab
        items={[latin, cyrillic]}
        list={[latin, cyrillic]}
        sort="title"
        density="full"
        query=""
        selected={new Set()}
        toggleSelect={() => {}}
        detailPath=""
        onDetail={() => {}}
        yt={{ ytData: vi.fn(async () => []), findAlbumTwin: vi.fn(), ytArtistAlbums: vi.fn(), refreshAfterYtDownload: vi.fn(), connected: null, epoch: 0 } as unknown as YtApi}
        actions={ACTIONS}
        onCount={() => {}}
      />,
    );

    await waitFor(() => expect(cardPaths()).toEqual(["/lib/cyrillic.mp3", "/lib/latin.mp3"]));
    await changeLanguage("ru");
    await waitFor(() => expect(cardPaths()).toEqual(["/lib/latin.mp3", "/lib/cyrillic.mp3"]));
  });
});
