import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusLine } from "../src/components/ui/StatusLine";

describe("StatusLine", () => {
  it("renders a terminal marker without hiding the status text", () => {
    render(<StatusLine kind="danger">Не удалось скачать</StatusLine>);

    expect(screen.getByText("[!!]")).toBeInTheDocument();
    expect(screen.getByText("Не удалось скачать")).toBeInTheDocument();
  });
});
