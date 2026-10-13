/* DTO экранного слоя YouTube Music (зеркало src/web/serialize.py). */

import type { RenderableMessage } from "../../i18n/messages";

export interface YTMTrack {
  video_id: string;
  title?: string;
  artist?: string;
  album_artist?: string;
  album?: string;
  year?: string | number;
  track_number?: string | number;
  cover_url?: string;
  duration?: number;
  video_type?: string;
  in_library?: boolean;
}

export interface YTMAlbum {
  id: string;
  title?: string;
  artist?: string;
  year?: string | number;
  track_count?: number;
  cover_url?: string;
  in_library_tracks?: number;
  in_library?: boolean;
}

export interface YTMAlbumDetail extends YTMAlbum {
  tracks: YTMTrack[];
}

export interface YTMArtist {
  id: string;
  name?: string;
  subscribers?: string;
  cover_url?: string;
  local_count?: number;
  in_library?: boolean;
}

export interface YTMArtistDetail {
  id: string;
  name?: string;
  subscribers?: string;
  cover_url?: string;
  top_songs: YTMTrack[];
  albums: YTMAlbum[];
}

export interface YTMPlaylist {
  id: string;
  title?: string;
  count?: number;
  cover_url?: string;
  description?: string;
  local_count?: number;
  in_library?: boolean;
}

export interface YTMPlaylistDetail extends YTMPlaylist {
  track_count: number;
  tracks: YTMTrack[];
}

/* Ответ POST /api/ytmusic/download. */
export interface YtmDownloadResult {
  ok: number;
  errors: number;
  archive?: string;
  items?: { video_id: string; ok: boolean; path?: string; error?: RenderableMessage; kept_clip?: boolean }[];
}
