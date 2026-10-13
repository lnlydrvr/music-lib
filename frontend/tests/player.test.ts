import { beforeEach, describe, expect, it, vi } from "vitest";
import { attachAudio, onAudio, usePlayer } from "../src/stores/player";

/* Фейковый <audio>: EventTarget + методы pause/play. */
function fakeAudio() {
  const el = new EventTarget() as EventTarget & {
    paused: boolean;
    play: () => void;
    pause: () => void;
  };
  el.paused = true;
  el.play = vi.fn(() => {
    el.paused = false;
  });
  el.pause = vi.fn(() => {
    el.paused = true;
  });
  return el;
}

beforeEach(() => {
  attachAudio(null);
  usePlayer.setState({ src: "", title: "", artist: "", coverUrl: "", visible: false, seq: 0 });
});

describe("player store", () => {
  it("play наполняет состояние и показывает бар", () => {
    usePlayer.getState().play({ src: "/api/preview/x", title: "Песня", artist: "Артист", coverUrl: "/c.jpg" });
    const s = usePlayer.getState();
    expect(s.src).toBe("/api/preview/x");
    expect(s.title).toBe("Песня");
    expect(s.artist).toBe("Артист");
    expect(s.coverUrl).toBe("/c.jpg");
    expect(s.visible).toBe(true);
    expect(s.seq).toBe(1);
  });

  it("play без src игнорируется", () => {
    usePlayer.getState().play({ src: "" });
    expect(usePlayer.getState().visible).toBe(false);
  });

  it("повторный play того же src инкрементит seq (перезапуск)", () => {
    usePlayer.getState().play({ src: "/a" });
    usePlayer.getState().play({ src: "/a" });
    expect(usePlayer.getState().seq).toBe(2);
  });

  it("hide ставит pause и прячет бар", () => {
    const el = fakeAudio();
    attachAudio(el as unknown as HTMLAudioElement);
    usePlayer.getState().play({ src: "/a" });
    usePlayer.getState().hide();
    expect(usePlayer.getState().visible).toBe(false);
    expect(el.pause).toHaveBeenCalled();
  });

  it("onAudio: подписка получает события, отписка глушит", () => {
    const el = fakeAudio();
    attachAudio(el as unknown as HTMLAudioElement);
    const fn = vi.fn();
    const off = onAudio("play", fn);
    el.dispatchEvent(new Event("play"));
    expect(fn).toHaveBeenCalledTimes(1);
    off();
    el.dispatchEvent(new Event("play"));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("onAudio видит ended", () => {
    const el = fakeAudio();
    attachAudio(el as unknown as HTMLAudioElement);
    const fn = vi.fn();
    onAudio("ended", fn);
    el.dispatchEvent(new Event("ended"));
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
