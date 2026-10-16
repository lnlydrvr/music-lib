# Product overview

## Purpose

`music-lib` is a local web app for everyday music library management. It brings
music search, file downloads, metadata preparation, and local collection
organization together in one interface.

The main user workflow is:

1. Find a track on YouTube or YouTube Music.
2. Review and, if needed, complete its tags, cover art, and lyrics.
3. Download the file and move it into the library.
4. Check the library and apply suggested fixes when needed.

The app also helps maintain an existing collection: it analyzes files and tags,
finds duplicates, identifies missing fields, and suggests normalization.

## Audience

The product is for people who keep their own music collection and want to manage
files rather than only browse a streaming catalog. Their main tasks are
organizing local audio files, correcting metadata, and connecting the collection
to YouTube Music catalogs or accounts.

The app runs locally and is accessed through a browser. Installation and usage
instructions are in the root [`README.md`](../../README.md).

## Main workflows

### Search and download

Users can search YouTube Music or YouTube. YouTube Music is the default source
and can be changed in settings. Search and tagging use data from the selected
source; audio downloads are handled by `yt-dlp`. When the corresponding setting
is enabled, a YouTube Music video is replaced with a matching Topic audio
version when available.

### Lucida downloads

The Lucida tab supports searching and downloading individual tracks and albums
from Qobuz and Amazon through Lucida. It does not support playlists. It is a
private, local-use integration: users are responsible for ensuring that their
use of third-party services and content is authorized. The app does not claim
to grant rights to third-party services or content.

Lucida access is prepared explicitly in a visible Playwright Chromium window.
The launcher attempts to install Chromium when Playwright is available and the
browser is missing; it can also be installed manually with
`playwright install chromium`. Setup requires a local graphical desktop session.
The status check reports
whether Playwright and Chromium are available without launching a browser. If
access is missing or expires, search and download fail immediately and direct
the user to prepare access; they never launch a browser implicitly. Completed
downloads are written to the library `Inbox` before placement is attempted. A
skipped or failed placement leaves the completed file in `Inbox` for recovery.
The selected service, optional storefront country, and bounded download
concurrency are configurable in Settings.

### Metadata preparation

Metadata can be fetched from iTunes, Deezer, and Discogs. Users choose which
sources are active and their order. The editor supports tags, cover art, and
lyrics, and can apply operations to multiple tracks at once.

### Library organization

The library directory is configured in settings or with `MUSIC_LIB_DIR`. Files
can be organized by artist and album, sorted, searched, and merged into albums.
Playlists are stored as M3U8 archives. Shazam import reads a text file of
`Title — Artist` entries; by default the file is stored in the library's hidden
`.system` directory, or users can select a custom file in Settings.

### Quality checks

The issues section combines file integrity checks with tag diagnostics. Before
applying bulk changes, users can review a plan and any conflicts. A conflict on
one item should not block unrelated fixes.

### YouTube Music integration

After authorization, the app shows account catalogs and lists, including liked
tracks, albums, artists, and playlists. Matches with local files are marked for
convenience. Recommendations are based on library tracks; depending on settings,
user actions can send likes, dislikes, or save tracks to the account library.

### Shazam import

Users can provide a text file with lines in `Title — Artist` format. The app
searches for matches and lets users continue to download a selected track.

## Product principles

1. **The library stays local.** The app works with files in the user's chosen
   directory.
2. **Changes are reviewable.** Bulk fixes are presented as a plan before they
   are applied.
3. **Long-running operations are observable.** Background tasks show progress,
   results, and errors.
4. **Safe defaults matter.** The server listens on the loopback interface
   `127.0.0.1` by default; network access requires an explicit host override.
5. **External services are not guaranteed.** Search, metadata, authorization,
   and recommendations depend on third-party API availability and behavior.

## Scope and limitations

- The app is not a streaming music service and does not host an audio catalog
  for users to listen to.
- The server does not provide user authentication. Running with
  `--host 0.0.0.0` exposes the API to other devices on the network and should be
  limited to trusted networks.
- YouTube Music features require separate authorization and may be affected by
  changes to the third-party service or the `ytmusicapi` library.
- Search, downloads, metadata, and lyrics depend on external services and
  network access.
- Lucida currently supports Qobuz and Amazon tracks and albums only, not
  playlists. It depends on Lucida, a valid prepared access clearance, and a
  locally usable Playwright Chromium browser; any of these may become
  unavailable or change without notice.
- Visual themes and language choices may evolve. Current interface guidelines
  are in [`DESIGN.md`](DESIGN.md); implementation details are in the source
  code.
- The repository does not currently include a license file, so distribution
  terms have not been defined.
