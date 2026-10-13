import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DialogProvider } from "../src/components/dialogs/DialogProvider";
import { changeLanguage } from "../src/i18n";
import { compressPaths, viewLyrics } from "../src/views/library/trackDetail";

const { get, startJob } = vi.hoisted(() => ({ get: vi.fn(), startJob: vi.fn() }));

vi.mock("../src/lib/api", () => ({ get, post: vi.fn(), del: vi.fn(), coverUrl: vi.fn() }));
vi.mock("../src/lib/jobs", () => ({ startJob }));
vi.mock("../src/lib/toast", () => ({ toast: vi.fn() }));

describe("track detail helpers", () => {
  it("uses the active locale for an empty lyrics fallback", async () => {
    await changeLanguage("en");
    get.mockResolvedValue({ artist: "Artist X", title: "Song One" });
    render(<DialogProvider />);

    void viewLyrics("/library/Artist X/Song One.mp3");

    expect(await screen.findByText("No lyrics")).toBeInTheDocument();
  });

  it("keeps a structured compression label as data until the render boundary", async () => {
    await changeLanguage("en");
    startJob.mockResolvedValue({ label: { code: "jobs.compress.audio_result", message: "Audio compressed" }, done: 2, skipped: 1 });
    const op = { set: vi.fn(), go: vi.fn() };

    await compressPaths(["/library/Artist X/Song One.mp3"], vi.fn(), () => op);

    expect(op.set).toHaveBeenLastCalledWith(100, {
      code: "library.track_detail.compress_result",
       params: { label: { code: "jobs.compress.audio_result", message: "Audio compressed" }, done: 2, skipped: 1 },
    });
  });
});
