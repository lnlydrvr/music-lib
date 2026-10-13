import { lazy, Suspense, useEffect, useState, type ComponentType, type LazyExoticComponent, type MouseEvent } from "react";
import { useHashRoute } from "./hooks/useHashRoute";
import { useTheme } from "./hooks/useTheme";
import { useHotkeys } from "./lib/hotkeys";
import { ROUTE_IMPORTS, prefetchRoute } from "./lib/prefetch";
import type { RouteName } from "./routes";
import { Topbar } from "./components/Topbar";
import { Tabbar } from "./components/Tabbar";
import { MoreMenu } from "./components/MoreMenu";
import { DialogProvider } from "./components/dialogs/DialogProvider";
import { KeymapDialog } from "./components/dialogs/KeymapDialog";
import { CommandPalette } from "./components/CommandPalette";
import { PlayerBar } from "./components/PlayerBar";
import { DownloadsDock } from "./components/DownloadsDock";
import { AppToaster } from "./lib/toast";
import { Spinner } from "./components/ui/Spinner";
import { useTranslation } from "react-i18next";

/* Каждый экран — свой чанк (динамический import); общий код Rollup сам выносит
   в разделяемые чанки. Deep-links не страдают: параметры (?path=) живут в hash
   и читаются самими экранами после монтирования. Импортеры объявлены в
   lib/prefetch — оттуда же их греет навигация, lazy и префетч не расходятся. */
const VIEWS = Object.fromEntries(
  Object.entries(ROUTE_IMPORTS).map(([route, load]) => [route, lazy(load)]),
) as Record<RouteName, LazyExoticComponent<ComponentType>>;

export default function App() {
  const { t } = useTranslation();
  const route = useHashRoute();
  const { theme, toggle } = useTheme();
  const [moreOpen, setMoreOpen] = useState(false);
  const View = VIEWS[route];

  useHotkeys({ onToggleTheme: toggle });

  /* Прогрев самых ходовых экранов на праздном ходу: спиннер Suspense при
     первом переходе в библиотеку не мелькает. Один раз за сессию —
     prefetchRoute идемпотентен. */
  useEffect(() => {
    const warm = () => {
      prefetchRoute("library");
      prefetchRoute("menu");
    };
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(warm, { timeout: 2000 });
      return () => window.cancelIdleCallback(id);
    }
    const t = window.setTimeout(warm, 1500); // старые браузеры/jsdom
    return () => window.clearTimeout(t);
  }, []);

  const focusView = (e: MouseEvent<HTMLAnchorElement>) => {
    // Без смены hash: #view — не маршрут, якорь сломал бы роутер.
    e.preventDefault();
    document.getElementById("view")?.focus();
  };

  return (
    <DialogProvider>
      <a className="skip-link" href="#view" onClick={focusView}>
        {t("shell.skip_to_content")}
      </a>
      <Topbar route={route} theme={theme} onToggleTheme={toggle} />
      {/* key по маршруту перезапускает stagger-анимацию входа (.enter) */}
      <main id="view" key={route} tabIndex={-1} className="enter">
        {/* Один Suspense на все экраны: при догрузке ленивого чанка остальной
            шелл (топбар, плеер, док загрузок) остаётся смонтированным. */}
        <Suspense fallback={<Spinner />}>
          <View />
        </Suspense>
      </main>
      <Tabbar
        route={route}
        moreOpen={moreOpen}
        onToggleMore={() => setMoreOpen((v) => !v)}
        onNavigate={() => setMoreOpen(false)}
      />
      <MoreMenu route={route} open={moreOpen} onClose={() => setMoreOpen(false)} />
      <PlayerBar />
      <DownloadsDock />
      <KeymapDialog />
      <CommandPalette />
      <AppToaster />
    </DialogProvider>
  );
}
