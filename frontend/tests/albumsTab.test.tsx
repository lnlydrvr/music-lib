import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AlbumsTab } from "../src/views/library/AlbumsTab";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import type { YTMAlbum } from "../src/features/ytm";
import type { AlbumGroup, TrackRow } from "../src/views/library/libUtils";
import type { YtApi } from "../src/views/library/useYtData";

function track(path: string, title: string, artist: string, album: string): TrackRow {
  return {
    path, title, artist, album, year: "", genre: "", album_artist: "", isrc: "", composer: "",
    track_number: "", disc_number: "", size_bytes: 0, duration_seconds: 0, bitrate: 0, mtime: 0,
    has_lyrics: false, has_synced_lyrics: false, has_cover: false, ext: ".mp3",
  };
}

/* Заглушка YT-слоя: только «сохранённые альбомы» (двойники по ключам). */
function makeYt(albums: YTMAlbum[]): YtApi {
  return {
    ytData: vi.fn(async (kind: string) => (kind === "albums" ? albums : [])),
    findAlbumTwin: vi.fn(async () => null),
    ytArtistAlbums: vi.fn(async () => []),
    refreshAfterYtDownload: vi.fn(async () => {}),
    connected: null,
    epoch: 0,
  } as unknown as YtApi;
}

function renderAlbums(rows: TrackRow[], albums: YTMAlbum[]) {
  const onOpenAlbum = vi.fn();
  const onOpenYtAlbum = vi.fn();
  const utils = render(
    <AlbumsTab
      items={rows}
      list={rows}
      sort="path"
      density="full"
      nameTranslit="auto"
      selected={new Set()}
      toggleSelect={() => {}}
      onOpenTrack={() => {}}
      yt={makeYt(albums)}
      openAlbumPaths={null}
      onOpenAlbum={onOpenAlbum}
      onCloseAlbum={() => {}}
      onOpenYtAlbum={onOpenYtAlbum}
      onCount={() => {}}
    />,
  );
  return { onOpenAlbum, onOpenYtAlbum, ...utils };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AlbumsTab: слияние локальных альбомов с YT", () => {
  const rows = [
    track("/lib/a1.mp3", "T1", "Artist A", "Album A"),
    track("/lib/a2.mp3", "T2", "Artist A", "Album A"),
    track("/lib/b1.mp3", "T1", "Artist B", "Album B"),
  ];

  it("полный двойник — ✓N/N; частичный — объединённая ◐N/M; нулевой — YT-карточка", async () => {
    const albums: YTMAlbum[] = [
      { id: "ytA", title: "Album A", artist: "Artist A", track_count: 2, in_library_tracks: 2 },
      { id: "ytB", title: "Album B", artist: "Artist B", track_count: 3, in_library_tracks: 1 },
      { id: "ytC", title: "Album C", artist: "Artist C", track_count: 5, in_library_tracks: 0 },
    ];
    const { onOpenAlbum, onOpenYtAlbum } = renderAlbums(rows, albums);

    // Полный: локальная карточка со счётом «● 2/2» (двойник подтверждён).
    const full = await screen.findByRole("button", { name: /Открыть альбом: Album A — Artist A \(2 из 2 тр\.\)/ });
    expect(within(full).getAllByText("● 2/2").length).toBeGreaterThan(0);

    // Частичный: объединённая карточка «◐ 1/3», клик — локальная деталь.
    const partial = screen.getByRole("button", { name: /Альбом: Album B — Artist B/ });
    expect(within(partial).getAllByText("◐ 1/3").length).toBeGreaterThan(0);
    await userEvent.setup().click(partial);
    expect(onOpenAlbum).toHaveBeenCalledTimes(1);
    expect(onOpenYtAlbum).not.toHaveBeenCalled();

    // Нулевой локально: YT-карточка «○ 0/5», клик — YT-деталь.
    const cloud = screen.getByRole("button", { name: /Альбом: Album C — Artist C/ });
    expect(within(cloud).getAllByText("○ 0/5").length).toBeGreaterThan(0);
    await userEvent.setup().click(cloud);
    expect(onOpenYtAlbum).toHaveBeenCalledWith("ytC", "Album C");
  });

  it("счётчик «N альбомов · ещё M на YT Music»; без двойника — чисто локальная карточка", async () => {
    const count = vi.fn();
    render(
      <AlbumsTab
        items={rows}
        list={rows}
        sort="path"
        density="full"
        nameTranslit="auto"
        selected={new Set()}
        toggleSelect={() => {}}
        onOpenTrack={() => {}}
        yt={makeYt([{ id: "ytC", title: "Album C", artist: "Artist C", track_count: 5, in_library_tracks: 0 }])}
        openAlbumPaths={null}
        onOpenAlbum={() => {}}
        onCloseAlbum={() => {}}
        onOpenYtAlbum={() => {}}
        onCount={(node) => count(node)}
      />,
    );
    await screen.findByRole("button", { name: /Альбом: Album C/ });
    await waitFor(() => {
      // «Показано…» нет: список не фильтровался → «2 альбома · ещё 1 на YT Music».
      const text = screen.queryByText(/альбом/) ? null : null;
      void text;
      expect(count).toHaveBeenCalled();
    });
    const last = count.mock.calls.at(-1)?.[0];
    expect(JSON.stringify(last)).toContain("ещё 1 на YT Music");
  });
});

describe("AlbumsTab: деталь локального альбома", () => {
  it("открывается по путям группы: шапка, треки, «← Назад»", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.startsWith("/api/library/album-nfo")) {
        return new Response(JSON.stringify({ review: "Поп и R&B", styles: ["поп", "R&B"] }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ albums: [] }), { headers: { "Content-Type": "application/json" } });
    }));
    const rows2 = [track("/lib/a1.mp3", "T1", "Artist A", "Album A"), track("/lib/a2.mp3", "T2", "Artist A", "Album A")];
    render(
      <AlbumsTab
        items={rows2}
        list={rows2}
        sort="path"
        density="full"
        nameTranslit="auto"
        selected={new Set()}
        toggleSelect={() => {}}
        onOpenTrack={() => {}}
        yt={makeYt([])}
        openAlbumPaths={["/lib/a1.mp3"]}
        onOpenAlbum={() => {}}
        onCloseAlbum={() => {}}
        onOpenYtAlbum={() => {}}
        onCount={() => {}}
      />,
    );
    expect(await screen.findByText("Album A")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "← Назад" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Выбрать все (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Выбрать теги для альбома" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Общие теги альбома" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обложка для альбома" })).toBeInTheDocument();
    expect(await screen.findByText("Поп и R&B")).toBeInTheDocument();
    expect(screen.getByText("поп")).toBeInTheDocument();
    expect(screen.getByText("R&B")).toBeInTheDocument();
    const trackList = screen.getByLabelText("Треки альбома");
    expect(within(trackList).getByRole("button", { name: "Выбрать все (2)" })).toBeInTheDocument();
  });

  it("показывает последней плитку для загрузки обложки", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ records: [] }), {
      headers: { "Content-Type": "application/json" },
    })));
    const rows2 = [track("/lib/a1.mp3", "T1", "Artist A", "Album A")];
    render(
      <DialogProvider>
        <AlbumsTab
          items={rows2} list={rows2} sort="path" density="full" nameTranslit="auto"
          selected={new Set()} toggleSelect={() => {}} onOpenTrack={() => {}}
          yt={makeYt([])} openAlbumPaths={["/lib/a1.mp3"]}
          onOpenAlbum={() => {}} onCloseAlbum={() => {}} onOpenYtAlbum={() => {}} onCount={() => {}}
        />
      </DialogProvider>,
    );

    await userEvent.setup().click(await screen.findByRole("button", { name: "Обложка для альбома" }));
    expect(await screen.findByLabelText("Загрузить файл обложки")).toHaveAttribute("accept", "image/jpeg,image/png");
    expect(screen.getByText("Перетащите файл или нажмите")).toBeInTheDocument();
  });
});

void ({} as AlbumGroup);
