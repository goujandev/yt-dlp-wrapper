# GrabIt.

A small Windows desktop app that wraps [yt-dlp](https://github.com/yt-dlp/yt-dlp)
and ffmpeg, so you can download a video by pasting a link — no terminal, no
flags, no install steps.

Paste a link → pick a quality → pick a folder → Download.

Licensed under [GPL-3.0](LICENSE).

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

Grab `GrabIt.exe` and double-click it. Python, Qt, yt-dlp and ffmpeg are all
bundled inside, so there is nothing else to install.

The exe is unsigned, so Windows shows a **"Windows protected your PC"** screen
the first time. Click **More info -> Run anyway**. First launch takes a few
seconds while it unpacks.

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

Roughly 80 MB, because it contains Python, PyQt6, yt-dlp and ffmpeg.

Options:

| Flag | Effect |
| --- | --- |
| `--clean` | delete `build/` and `dist/` first |
| `--no-ffmpeg` | skip the ffmpeg download; produces a much smaller exe that needs ffmpeg on the user's machine |

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

## Releasing

1. `python build.py --clean`
2. Check `dist/` contains **GrabIt.exe** and **THIRD-PARTY-NOTICES.txt**
3. Tag and push: `git tag v1.0.0 && git push origin v1.0.0`
4. Create the GitHub release and attach **both** files from `dist/`

Attaching the notices file matters — it is what keeps the GPL ffmpeg binary
inside the exe properly licensed. Bump `__version__` in `grabit/__init__.py`
when you cut a new version.

Tell people the first launch shows a SmartScreen warning (the exe is unsigned):
**More info -> Run anyway**. Signing is the only real fix.

## License

GrabIt is licensed under the **GNU General Public License v3.0** - see
[LICENSE](LICENSE).

It has to be. GrabIt links PyQt6, which is GPLv3, so any distributed build must
also be GPLv3 and ship its source. Publishing this repository satisfies that.

To relicense GrabIt under something permissive you would need to drop PyQt6 -
porting `ui.py` and `worker.py` to **PySide6** (LGPLv3) is mostly import
renames, since neither uses PyQt-specific APIs - or buy a Riverbank commercial
PyQt licence.

### Bundled components

`THIRD-PARTY-NOTICES.txt` ships inside the exe and next to it. It covers:

| Component | License |
| --- | --- |
| FFmpeg (gyan.dev essentials build) | GPLv3+ |
| PyQt6 / Qt6 | GPLv3 / LGPLv3 |
| yt-dlp | The Unlicense |
| Python | PSF License v2 |

FFmpeg is run as a separate process, so only its own binary is covered by its
license.

### A note on use

GrabIt is a front-end for yt-dlp; it does not host, bypass, or decrypt
anything. Downloading may still breach a site's terms of service or copyright
law depending on the content and your country. That is on the person using it.

## Project layout

```
run_grabit.py        launcher / PyInstaller entry point
grabit/
  main.py            app bootstrap, Windows console suppression
  ui.py              MainWindow — widgets and signal wiring only
  theme.py           palette, the three type roles, the global stylesheet
  widgets.py         the blocky pieces Qt does not provide
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

## The look

Flat, dark, and blocky: a browser layout — tab strip, toolbar, page — drawn in
the Arch Linux palette. Nothing is rounded, surfaces are separated by 1px
hairlines rather than shadows, and the one accent (Arch blue `#1793D1`) is spent
only on state: the tab's top rule, a focused field's border, the selected row,
the primary button.

Two consequences show up in the code. Every colour and font decision lives in
`theme.py` as one style sheet, so no widget carries its own styling. And because
the style allows no floating system windows, `widgets.py` reimplements the two
things Qt would otherwise float: the quality dropdown (`BlockSelect`, a menu
built from our own rows) and message boxes (`BlockDialog`, a panel drawn over
the page). The folder picker stays native — like a browser, GrabIt hands that
one to the OS.

Icons come from Segoe Fluent Icons or Segoe MDL2 Assets, whichever Windows
provides; where neither exists the icon buttons fall back to text labels.

## Why the modules split this way

`downloader.py` knows nothing about Qt and
`ui.py` never blocks. Every slow call — reading a link, downloading — happens on
a `QThread` and reports back through signals, so the window stays responsive.
