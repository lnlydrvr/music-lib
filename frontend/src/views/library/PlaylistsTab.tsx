/* Вкладка «Плейлисты»: YT-плейлисты с local_count из локальных .m3u8-архивов. */
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { PlaylistRow } from "../../features/ytm/cards";
import { SkeletonRows } from "../../components/ui/SkeletonRows";
import type { YTMPlaylist } from "../../features/ytm/types";
import type { YtApi } from "./useYtData";

export function PlaylistsTab({
  query,
  yt,
  onOpenPlaylist,
  onCount,
}: {
  query: string;
  yt: YtApi;
  onOpenPlaylist: (id: string) => void;
  onCount: (node: ReactNode) => void;
}) {
  const { t } = useTranslation();
  const [playlists, setPlaylists] = useState<YTMPlaylist[] | null>(null);
  useEffect(() => {
    let alive = true;
    setPlaylists(null);
    yt.ytData<YTMPlaylist>("playlists").then((yt) => {
      if (alive) setPlaylists(yt);
    });
    return () => {
      alive = false;
    };
  }, [yt]);

  const q = query.toLowerCase();
  const shown = (playlists || []).filter(
    (pl) => !q || `${pl.title || ""} ${pl.description || ""}`.toLowerCase().includes(q),
  );

  useEffect(() => {
    onCount(t("library.playlists.count", { count: shown.length }));
  }, [shown.length, onCount, t]);

  /* YT-плейлисты грузятся отдельно от библиотеки: пока ответ в полёте —
     скелетон строк той же формы (PlaylistRow), а не пустой контент. */
  if (!playlists) return <SkeletonRows n={4} meta />;
  if (!shown.length) {
    return (
      <div className="empty">
        {yt.connected === false
          ? t("library.playlists.disconnected")
          : t("library.playlists.none")}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {shown.map((pl) => (
        <PlaylistRow key={pl.id} playlist={pl} onOpen={(p) => onOpenPlaylist(p.id)} />
      ))}
    </div>
  );
}
