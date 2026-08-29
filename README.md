# GrabIt

A small Windows desktop app that wraps [yt-dlp](https://github.com/yt-dlp/yt-dlp)
and ffmpeg, so you can download a video by pasting a link — no terminal, no
flags, no install steps.

Paste a link → pick a quality → pick a folder → Download.

## What v1 does

- Paste a video URL and fetch the qualities that link actually offers
- Simple quality presets: **Best available**, per-resolution (1080p, 720p, …),
  and **Audio only (MP3)**
- Native folder picker, remembers the last folder you used
- Live progress bar with size, speed and ETA
- Status/log panel showing each stage (reading link, downloading, merging with
  ffmpeg, done)
- Cancel button that stops cleanly and deletes the half-written files
- Friendly messages for bad links, dead videos, network drops and missing ffmpeg

Deliberately **not** in v1: playlists, subtitles, trimming.

## Using the built app

Grab `GrabIt.exe` and double-click it. ffmpeg is bundled inside, so there is
nothing else to install.

## Running from source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_grabit.py
```

From source, ffmpeg is not bundled. GrabIt looks for it in this order:

1. Inside the bundle (frozen builds only)
2. Next to `GrabIt.exe`, or in the project root / `vendor/` when run from source
3. Anywhere on your `PATH`

So either drop an `ffmpeg.exe` into `vendor/` (running `python build.py` once
fetches it for you), or install ffmpeg system-wide:

```bash
winget install Gyan.FFmpeg
```

Without ffmpeg the app still starts and warns you in the log; downloads that
need merging or MP3 conversion will fail with a clear message.

## Building the .exe

```bash
pip install -r requirements-dev.txt
python build.py
```

`build.py` downloads a static ffmpeg (~30 MB zipped, once) into `vendor/`, then
runs PyInstaller. The result is a single self-contained file:

```
dist\GrabIt.exe
```

Roughly 120 MB, because it contains Python, PyQt6, yt-dlp and ffmpeg.

Options:

| Flag | Effect |
| --- | --- |
| `--clean` | delete `build/` and `dist/` first |
| `--no-ffmpeg` | skip the ffmpeg download; produces a ~45 MB exe that needs ffmpeg on the user's machine |

To run PyInstaller directly instead:

```bash
pyinstaller GrabIt.spec --noconfirm
```

The spec bundles `vendor/ffmpeg.exe` if it is present and warns if it is not.

### Notes on the build

- The exe is windowed (`console=False`). `grabit/main.py` patches
  `subprocess.Popen` with `CREATE_NO_WINDOW` so ffmpeg does not flash a console.
- `yt_dlp.extractor.lazy_extractors` is listed as a hidden import — yt-dlp loads
  extractors dynamically and PyInstaller cannot see them.
- The app icon is generated from `logo.png` at build time: a multi-size
  `GrabIt.ico` is stamped into the exe, and a 256px PNG is bundled for the
  window and taskbar. Replace `logo.png` and rebuild to change it.
- Unused Qt modules (QML, Quick, WebEngine, Multimedia, …) are excluded to keep
  the exe smaller.
- Some antivirus tools flag unsigned PyInstaller one-file exes. Code-signing is
  the real fix; a `--onedir` build (drop `runtime_tmpdir`, use `COLLECT`) trips
  it less often.

## Licensing (read before sharing the exe)

GrabIt bundles GPL-licensed components, so if you distribute `GrabIt.exe` to
anyone else:

- Ship `THIRD-PARTY-NOTICES.txt` alongside the exe (it is also bundled inside).
  It carries ffmpeg's GPLv3 notice and the written offer for its source.
- **PyQt6 is GPLv3 too.** Unlike ffmpeg, it is linked into GrabIt rather than
  run as a separate process — so distributing this build obliges you to release
  GrabIt's own source under the GPL. Using it privately imposes nothing.

To distribute GrabIt without opening its source, either buy a Riverbank
commercial PyQt licence, or port the UI to **PySide6** (LGPLv3), which permits
closed-source distribution. The port is mostly import renames, as `ui.py` and
`worker.py` use no PyQt-specific APIs.

## Project layout

```
run_grabit.py        launcher / PyInstaller entry point
grabit/
  main.py            app bootstrap, Windows console suppression
  ui.py              MainWindow — widgets and signal wiring only
  worker.py          QThread wrappers: ProbeWorker, DownloadWorker
  downloader.py      yt-dlp logic (Qt-free), presets, error translation
  ffmpeg_tools.py    finding ffmpeg
  resources.py       finding bundled assets (icons)
logo.png             source logo; build.py renders the icons from it
assets/              generated GrabIt.ico + icon.png (gitignored)
GrabIt.spec          PyInstaller spec
build.py             fetch ffmpeg + build in one command
vendor/              ffmpeg.exe lands here (gitignored)
```

The split matters for one reason: `downloader.py` knows nothing about Qt and
`ui.py` never blocks. Every slow call — reading a link, downloading — happens on
a `QThread` and reports back through signals, so the window stays responsive.
