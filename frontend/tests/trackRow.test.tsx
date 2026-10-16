import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrackRow } from "../src/components/ui/TrackRow";

describe("TrackRow", () => {
  it("does not add a tab stop when the row has no action", () => {
    render(<TrackRow title="Track title" sub="Artist" />);

    expect(screen.getByText("Track title").closest(".trackrow")).not.toHaveAttribute("tabindex");
  });
});
