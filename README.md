# music-lib

```text
                  _         ___ __
  __ _  __ _____ (_)_______/ (_) /
 /  ' \/ // (_-</ / __/___/ / / _ \
/_/_/_/\_,_/___/_/\__/   /_/_/_.__/
```

A local web app for managing your music library. Find and download tracks, edit
tags, cover art, and lyrics, organize files, and check your library for issues.

The app runs on your computer and opens in a web browser. By default, the server
is available only at `127.0.0.1`.

The interface languages are listed in `frontend/src/locales/registry.json`; choose
one in Settings.

**Documentation:** [English](docs/en/README.md) · [Русский](docs/ru/README.md)

## Features

- Search for and download audio from YouTube and YouTube Music.
- Search and download individual Qobuz and Amazon tracks or albums through
  Lucida.
- Fetch metadata and cover art from iTunes, Deezer, and Discogs.
- Edit tags and cover art; find and update lyrics.
- Browse your library by albums, artists, tracks, and playlists.
- Organize files into folders, find duplicates, merge albums, check tags, and
  apply suggested fixes.
- Import Shazam lists in `Title — Artist` format.
- Get YouTube Music recommendations based on your local library.
- Configure audio format and quality, metadata sources, search source, Lucida
  service and download concurrency, and other download behavior.

## Requirements

- Python 3.10 or later.
- Node.js with npm: version 20.19+ in the 20.x line, 22.12+ in the 22.x line,
  or 24+. The launcher uses Node.js to install dependencies and build the UI.
- `ffmpeg` is needed for audio conversion and compression features.
- Network access for search, downloads, and external services.

Python dependencies are defined in `pyproject.toml`. Frontend dependencies are
locked in `frontend/package-lock.json`.

## Installation

Clone the repository, create a virtual environment, and install the app:

```bash
git clone <repository-url>
cd music-lib
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

If you use `uv` and want to install the versions recorded in `uv.lock`, run
`uv sync --locked` from the repository root. This creates or updates the
project's `.venv` and includes the default `dev` dependency group. The
`uv pip install -e .` command is also supported in an active virtual
environment, but it reads dependencies from `pyproject.toml` and does not
consume `uv.lock`. The standard launcher installs Chromium for Lucida when
Playwright is available and Chromium is missing. To install it manually, run
`playwright install chromium`.

On Windows, activate the environment with `.venv\Scripts\activate`.

## Running the app

The recommended option is the launcher. It installs frontend dependencies and
builds the UI when needed, then starts the server:

```bash
python scripts/run.py
```

The launcher prints the app URL and usually opens it in your browser. Options:

```bash
python scripts/run.py --port 9000       # use the specified port
python scripts/run.py --no-browser      # do not open a browser automatically
python scripts/run.py --host 0.0.0.0    # allow access from your local network
```

With `--host 0.0.0.0`, other devices on your network can access the app. Use
this mode only on a trusted network: the app does not require a user account or
provide network authentication.

For frontend development, run FastAPI and Vite together:

```bash
python scripts/dev.py
```

Open the Vite URL printed by the command (usually `http://127.0.0.1:5173`).

Running the server directly with `python app.py` does not build the frontend.
Build it first to use the full web interface:

```bash
cd frontend
npm ci
npm run build
cd ..
python app.py
```

The `music-lib` command is also available after installing with `pip install -e .`.

### Lucida access setup

Lucida access is prepared explicitly in a visible Chromium window. From the
Lucida tab, choose **Prepare access** and complete the access challenge. This
requires a local graphical desktop session. Search and download do not launch a
browser implicitly; if access expires, prepare it again. The status check does
not launch a browser.

If Chromium was not installed by the launcher, install it with:

```bash
playwright install chromium
```

Lucida supports individual tracks and albums from the selected Qobuz or Amazon
service, not playlists. Completed files are first saved to `Inbox`; if moving a
file into the library is skipped or fails, it remains there.

## Music library directory

Choose the library directory in the app settings or set it with the
`MUSIC_LIB_DIR` environment variable. If unset, the app uses the path in
`~/.config/music-lib/config.json`; if no path is configured, it selects a
writable iCloud folder or `~/Music`. The legacy `MUSIC_DL_DIR` variable is also
supported as a fallback.

New downloads first go to `Inbox`. Files placed in the library are usually
organized by artist and album:

```text
Music/
├── Inbox/
└── Artist/
    └── Album/
        └── Track.m4a
```

Playlist M3U8 archives are stored in the `Playlists` directory inside the
library. Shazam import defaults to a text file under the hidden `.system`
directory in the library; a custom file can be selected in Settings.

## YouTube Music

YouTube Music integration requires authorization. Configure it in Settings;
the app supports OAuth device flow and browser-header authentication. The default
authorization file is `~/.config/music-lib/ytmusic_auth.json`. The main search
source can be changed between YouTube Music and YouTube in Settings.

Feature availability depends on the connected account and the external API.
On macOS, extracting browser cookies may prompt for Keychain access. YouTube
downloads may also require valid cookies, configurable in Settings.

## Tests and checks

Run Python tests from the repository root:

```bash
pytest
```

Run frontend tests from `frontend` (after `npm ci`):

```bash
npm test
```

Check types and create a production frontend build:

```bash
cd frontend
npm run build
```

## License

The repository does not currently include a `LICENSE` file, so the terms for
use and distribution have not been defined.

## Acknowledgments

Thanks to [init.Made](https://initmade.com) for the UI inspiration.
