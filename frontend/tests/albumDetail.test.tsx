import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { changeLanguage } from "../src/i18n";
import { AlbumDetailLocal } from "../src/views/library/albumDetail";
import { ALBUM_COMMON_TAG_FIELDS, type AlbumGroup } from "../src/views/library/libUtils";

vi.mock("../src/lib/api", () => ({
  coverUrl: (path: string) => `/covers/${path}`,
  get: vi.fn(() => Promise.resolve({})),
  post: vi.fn(),
}));

const album: AlbumGroup = {
  key: "album::Album X::Artist X",
  title: "Album X",
  artist: "Artist X",
  paths: ["/library/Artist X/Song One.mp3"],
  coverPath: null,
  tracks: [{
    path: "/library/Artist X/Song One.mp3", title: "Song One", artist: "Artist X", album: "Album X",
    year: "2024", genre: "Rock", album_artist: "Artist X", isrc: "", composer: "", track_number: "1",
    disc_number: "1", size_bytes: 1, duration_seconds: 1, bitrate: 320, mtime: 0, has_lyrics: false,
    has_synced_lyrics: false, has_cover: false, ext: ".mp3",
  }],
};

function renderAlbumDetail() {
  const yt = { findAlbumTwin: vi.fn().mockResolvedValue(null) } as never;
  return render(
    <AlbumDetailLocal
      g={album}
      selected={new Set()}
      toggleSelect={vi.fn()}
      onBack={vi.fn()}
      onOpenTrack={vi.fn()}
      yt={yt}
      actions={{ load: vi.fn(), openYtAlbum: vi.fn() }}
    />,
  );
}

afterEach(() => vi.clearAllMocks());

describe("AlbumDetailLocal localization", () => {
  it("rerenders owned album copy on a locale switch while preserving album metadata", async () => {
    await changeLanguage("ru");
    renderAlbumDetail();

    expect(screen.getByRole("region", { name: "Альбом" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "← Назад" })).toBeInTheDocument();
    expect(screen.getAllByText("Album X")).not.toHaveLength(0);

    await changeLanguage("en");

    expect(screen.getByRole("region", { name: "Album" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "← Back" })).toBeInTheDocument();
    expect(screen.getAllByText("Album X")).not.toHaveLength(0);
  });

  it("keeps common album tag fields as stable API IDs", () => {
    expect(ALBUM_COMMON_TAG_FIELDS).toEqual([
      "artist", "album", "album_artist", "year", "genre", "isrc", "composer", "publisher", "comment",
    ]);
  });
});
