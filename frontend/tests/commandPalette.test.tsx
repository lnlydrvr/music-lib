import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CommandPalette } from "../src/components/CommandPalette";
import { useHotkeys } from "../src/lib/hotkeys";
import { useOverlays } from "../src/stores/overlays";

/* cmdk Command.List использует ResizeObserver и scrollIntoView
   выбранного пункта — в jsdom их нет. */
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
const origScrollIntoView = Element.prototype.scrollIntoView;

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", RO);
  Element.prototype.scrollIntoView = () => {};
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (origScrollIntoView) Element.prototype.scrollIntoView = origScrollIntoView;
  else delete (Element.prototype as Partial<Element>).scrollIntoView;
  useOverlays.setState({ commandOpen: false, keymapOpen: false, dialogCount: 0 });
  location.hash = "";
});

function Probe() {
  useHotkeys({ onToggleTheme: () => {} });
  return null;
}

describe("CommandPalette (cmdk)", () => {
  it("Cmd+K открывает и закрывает палитру, Esc — закрывает", async () => {
    render(
      <>
        <Probe />
        <CommandPalette />
      </>,
    );
    expect(useOverlays.getState().commandOpen).toBe(false);

    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(useOverlays.getState().commandOpen).toBe(true);
    expect(await screen.findByPlaceholderText("Поиск команды…")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(useOverlays.getState().commandOpen).toBe(false));

    /* Нелатинская раскладка: key ≠ «k», но code — физическая клавиша K. */
    fireEvent.keyDown(document, { key: "л", code: "KeyK", metaKey: true });
    await waitFor(() => expect(useOverlays.getState().commandOpen).toBe(true));
    fireEvent.keyDown(document, { key: "л", code: "KeyK", metaKey: true });
    await waitFor(() => expect(useOverlays.getState().commandOpen).toBe(false));

    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    await waitFor(() => expect(useOverlays.getState().commandOpen).toBe(true));
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    await waitFor(() => expect(useOverlays.getState().commandOpen).toBe(false));
  });

  it("пункты «Переход» навигируют и закрывают палитру", async () => {
    render(<CommandPalette />);
    useOverlays.getState().setCommandOpen(true);

    const item = await screen.findByText("Библиотека");
    fireEvent.click(item);
    expect(location.hash).toBe("#/library");
    await waitFor(() => expect(useOverlays.getState().commandOpen).toBe(false));
  });

  it("«Горячие клавиши» открывают keymap-оверлей", async () => {
    render(
      <>
        <CommandPalette />
      </>,
    );
    useOverlays.getState().setCommandOpen(true);

    fireEvent.click(await screen.findByText("Горячие клавиши"));
    expect(useOverlays.getState().keymapOpen).toBe(true);
    expect(useOverlays.getState().commandOpen).toBe(false);
  });

  it("при открытой палитре цифры не переключают экран", async () => {
    render(
      <>
        <Probe />
        <CommandPalette />
      </>,
    );
    useOverlays.getState().setCommandOpen(true);
    await screen.findByPlaceholderText("Поиск команды…");

    fireEvent.keyDown(document, { key: "1" });
    expect(location.hash).not.toBe("#/menu");
  });
});
