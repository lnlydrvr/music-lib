import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const META_COLORS: Record<Theme, string> = { light: "#F5F7FA", dark: "#191919" };

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem("music-lib-theme", t);
  } catch {
    /* приватный режим — просто без сохранения */
  }
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", META_COLORS[t]);
}

/* Тема шелла: начальное значение выставил inline-скрипт в index.html. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => (t === "light" ? "dark" : "light"));
  }, []);

  return { theme, toggle };
}
