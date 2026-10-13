import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  AlbumCard,
  ArtistCard,
  CountBadge,
  DownloadAllButton,
  MinimalTrackRows,
  PlaylistRow,
  YtmTrackRow,
  type YTMAlbum,
  type YTMArtist,
  type YTMPlaylist,
  type YTMTrack,
  type YtmDownloadTarget,
} from "../src/features/ytm";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CountBadge", () => {
  it("● полный / ◐ частичный / ○ пусто / 0 тр.", () => {
    const { rerender } = render(<CountBadge have={5} total={5} />);
    expect(screen.getByText("● 5/5").className).toContain("ok");
    rerender(<CountBadge have={4} total={5} />);
    expect(screen.getByText("◐ 4/5").className).toContain("warn"); // >0.5 — жёлтый
    rerender(<CountBadge have={1} total={5} />);
    expect(screen.getByText("◐ 1/5").className).toContain("bad"); // ≤0.5 — красный
    rerender(<CountBadge have={0} total={5} />);
    expect(screen.getByText("○ 0/5").className).toContain("bad");
    rerender(<CountBadge have={0} total={0} />);
    expect(screen.getByText("0 тр.")).toBeInTheDocument();
  });
});

describe("AlbumCard", () => {
  const album: YTMAlbum = { id: "a1", title: "Альбом", artist: "Артист", track_count: 5, in_library_tracks: 2, cover_url: "http://c/1.jpg" };

  it("N/M-бейдж, открытие по клику и Enter", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<AlbumCard album={album} onOpen={onOpen} />);
    const card = screen.getByRole("button", { name: "Альбом: Альбом — Артист" });
    // Оверлей на обложке + подпись в строке — обе плашки N/M.
    expect(card.querySelector(".lib-album-badge")!.textContent).toBe("◐ 2/5");
    expect(within(card).getAllByText("◐ 2/5")).toHaveLength(2);
    await user.click(card);
    expect(onOpen).toHaveBeenCalledWith(album);
  });

  it("без локальных треков — «○ нет»", () => {
    render(<AlbumCard album={{ id: "a2", title: "X" }} onOpen={() => {}} />);
    expect(screen.getByText("○ нет", { selector: ".lib-album-badge" })).toBeInTheDocument();
  });
});

describe("ArtistCard", () => {
  it("локальные треки и подписка", () => {
    const artist: YTMArtist = { id: "ar1", name: "Имя", subscribers: "1 200", local_count: 3, in_library: true };
    render(<ArtistCard artist={artist} subscribed />);
    expect(screen.getByRole("button", { name: "Исполнитель: Имя" })).toBeInTheDocument();
    expect(screen.getByText("3 в библиотеке · подписан")).toBeInTheDocument();
    expect(screen.getByText("1 200 подписч.")).toBeInTheDocument();
  });

  it("без локальных треков — только «подписан»", () => {
    render(<ArtistCard artist={{ id: "ar2", name: "Другой" }} subscribed />);
    expect(screen.getByText("подписан")).toBeInTheDocument();
  });
});

describe("PlaylistRow", () => {
  it("N/M локального архива и число треков", async () => {
    const user = userEvent.setup();
    const pl: YTMPlaylist = { id: "p1", title: "Микс", count: 7, local_count: 2, description: "описание" };
    const onOpen = vi.fn();
    render(<PlaylistRow playlist={pl} onOpen={onOpen} />);
    const row = screen.getByRole("button", { name: /Микс/ });
    expect(within(row).getByText("◐ 2/7")).toBeInTheDocument();
    expect(within(row).getByText("7 треков")).toBeInTheDocument();
    await user.click(row);
    expect(onOpen).toHaveBeenCalledWith(pl);
  });
});

describe("YtmTrackRow", () => {
  const base: YTMTrack = { video_id: "v1", title: "Трек", artist: "Артист", year: 2020, duration: 100 };

  it("не в библиотеке — «Радио» и «Скачать»; клик скачивания", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    const onRadio = vi.fn();
    render(<YtmTrackRow track={base} onDownload={onDownload} onRadio={onRadio} />);
    expect(screen.getByRole("button", { name: "Похожие: Трек" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Скачать: Трек" }));
    expect(onDownload).toHaveBeenCalledWith(base);
    await user.click(screen.getByRole("button", { name: "Похожие: Трек" }));
    expect(onRadio).toHaveBeenCalledWith(base);
  });

  it("в библиотеке — бейдж вместо кнопки; клип помечается", () => {
    render(<YtmTrackRow track={{ ...base, in_library: true, video_type: "OMV" }} onDownload={() => {}} />);
    expect(screen.getByLabelText("В библиотеке")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Скачать: Трек" })).not.toBeInTheDocument();
    expect(screen.getByText("клип")).toBeInTheDocument();
  });
});

describe("MinimalTrackRows", () => {
  it("минимальные строки с номером, YT, длительностью; пусто без треков", () => {
    const tracks: YTMTrack[] = [
      { video_id: "v1", title: "A", artist: "X", track_number: "3", duration: 200, in_library: true },
      { video_id: "v2", title: "B", artist: "Y" },
    ];
    const { container } = render(<MinimalTrackRows tracks={tracks} onDownload={() => {}} />);
    const grid = container.querySelector(".lib-grid")!;
    expect(grid.getAttribute("data-density")).toBe("minimal");
    expect(container.querySelectorAll(".lib-card")).toHaveLength(2);
    expect(screen.getByTitle("Номер трека").textContent).toBe("3");
    expect(screen.getAllByTitle("Источник").length).toBe(2); // «YT» у каждой строки
    expect(screen.getByLabelText("В библиотеке")).toBeInTheDocument();
    expect(container.querySelector(".empty")).toBeNull();

    const { container: empty } = render(<MinimalTrackRows tracks={[]} onDownload={() => {}} />);
    expect(empty.querySelector(".empty")!.textContent).toBe("пусто");
  });
});

describe("DownloadAllButton", () => {
  it("считает отсутствующие и качает только их", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn(async () => {});
    const items: YTMTrack[] = [
      { video_id: "a", in_library: true },
      { video_id: "b" },
    ];
    const target = {
      kind: "playlist",
      providerId: "PL123",
      title: { code: "ytm.download.playlist_name", params: { title: "Плейлист" } },
    } satisfies YtmDownloadTarget;
    render(<DownloadAllButton items={items} target={target} onDownload={onDownload} />);
    const btn = screen.getByRole("button", { name: "Скачать отсутствующие (1)" });
    await user.click(btn);
    expect(onDownload).toHaveBeenCalledWith([{ video_id: "b" }], target);
  });

  it("всё в библиотеке — кнопка недоступна", () => {
    render(<DownloadAllButton items={[{ video_id: "a", in_library: true }]} target={{ kind: "playlist", providerId: "PL123", title: { code: "ytm.download.playlist_name", params: { title: "P" } } }} onDownload={() => {}} />);
    expect(screen.getByRole("button", { name: "Всё уже в библиотеке" })).toBeDisabled();
  });
});
