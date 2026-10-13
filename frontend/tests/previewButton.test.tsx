import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PreviewButton } from "../src/components/PreviewButton";
import { ApiError, get } from "../src/lib/api";
import { toast } from "../src/lib/toast";

vi.mock("../src/lib/api", async () => {
  const actual = await vi.importActual<typeof import("../src/lib/api")>("../src/lib/api");
  return { ...actual, get: vi.fn() };
});
vi.mock("../src/lib/toast", () => ({ toast: vi.fn() }));

beforeEach(() => {
  vi.mocked(get).mockReset();
  vi.mocked(toast).mockClear();
});

describe("PreviewButton", () => {
  it("passes an ApiError renderable descriptor to the toast", async () => {
    vi.mocked(get).mockRejectedValue(new ApiError({ code: "api.errors.file_not_found", params: { path: "/missing.mp3" }, message: "File not found: /missing.mp3" }));
    render(<PreviewButton url="https://example.test/track" />);

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(toast).toHaveBeenCalledWith(
      { code: "api.errors.file_not_found", params: { path: "/missing.mp3" }, message: "File not found: /missing.mp3" },
      "error",
    ));
  });

  it("passes a legacy provider error string to the toast unchanged", async () => {
    const providerError = "YouTube Music: unavailable in this region";
    vi.mocked(get).mockRejectedValue(new Error(providerError));
    render(<PreviewButton url="https://example.test/track" />);

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(toast).toHaveBeenCalledWith(providerError, "error"));
  });
});
