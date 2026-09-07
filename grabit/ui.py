"""The GrabIt main window.

Laid out like a browser: a tab strip, a toolbar holding the URL field, and the
page beneath them. The window owns the widgets and the two workers; all blocking
work lives in worker.py, so every method here returns immediately.
"""

from __future__ import annotations

import html
import os

from PyQt6.QtCore import QSettings, QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFontMetrics, QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, ORG_NAME, __version__, theme
from .ffmpeg_tools import find_ffmpeg
from .resources import WINDOW_ICON, resource_path
from .widgets import (
    BlockDialog,
    BlockSelect,
    Omnibox,
    action_button,
    icon_button,
    rule,
    section_label,
)
from .worker import DownloadWorker, ProbeWorker

STRIP_HEIGHT = 34
TAB_MAX_WIDTH = 360
TAB_PADDING = 28  # the 14px each side the style sheet gives the tab
NEW_TAB = "New download"

# Log tags are a fixed-width first column; the colour carries the severity.
LOG_TAG_WIDTH = 7
LOG_TONES = {"warn": theme.WARNING, "error": theme.DANGER}


def app_icon() -> QIcon:
    """The GrabIt icon, or an empty icon if the asset is missing."""
    path = resource_path(WINDOW_ICON)
    return QIcon(path) if path else QIcon()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(640, 560)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._probe_worker: ProbeWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._presets: list = []
        self._probed_url = ""
        self._titlebar_done = False

        self._build_ui()
        self._restore_output_dir()
        self._check_ffmpeg()
        self._update_buttons()

    # ---------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        central = QWidget()
        stack = QVBoxLayout(central)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)
        stack.addWidget(self._build_strip())
        stack.addWidget(self._build_toolbar())
        stack.addWidget(self._build_page(), 1)
        self.setCentralWidget(central)

    def _build_strip(self) -> QWidget:
        """The deepest strip. One tab, because there is one download at a time."""
        strip = QWidget()
        strip.setObjectName("strip")
        strip.setFixedHeight(STRIP_HEIGHT)

        row = QHBoxLayout(strip)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(0)

        self.tab_label = QLabel(NEW_TAB)
        self.tab_label.setObjectName("tab")
        self.tab_label.setMaximumWidth(TAB_MAX_WIDTH)
        row.addWidget(self.tab_label)
        row.addStretch(1)

        version = QLabel(f"{APP_NAME.lower()} {__version__}")
        version.setObjectName("version")
        row.addWidget(version)
        return strip

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        column = QVBoxLayout(toolbar)
        column.setContentsMargins(12, 8, 12, 8)
        column.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.omnibox = Omnibox("Paste a video link")
        self.url_edit = self.omnibox.edit
        self.url_edit.returnPressed.connect(self.on_fetch)
        self.url_edit.textChanged.connect(self.on_url_changed)
        self.fetch_button = action_button("Fetch")
        self.fetch_button.setMinimumWidth(92)
        self.fetch_button.clicked.connect(self.on_fetch)
        row.addWidget(self.omnibox, 1)
        row.addWidget(self.fetch_button)
        column.addLayout(row)

        # Length and uploader, once a link has been read. Hidden until then:
        # an empty row would be a label for something that does not exist.
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("detailText")
        self.detail_label.setVisible(False)
        column.addWidget(self.detail_label)

        self._toolbar = toolbar
        return toolbar

    def _build_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        column = QVBoxLayout(page)
        column.setContentsMargins(12, 12, 12, 12)
        column.setSpacing(0)

        column.addWidget(section_label("Quality"))
        column.addSpacing(6)
        self.quality_select = BlockSelect("Fetch a link first")
        column.addWidget(self.quality_select)

        column.addSpacing(14)
        column.addWidget(section_label("Save to"))
        column.addSpacing(6)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.folder_edit = QLineEdit()
        self.folder_edit.setObjectName("field")
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setFixedHeight(theme.ROW_HEIGHT)
        self.browse_button = icon_button(theme.ICON_FOLDER, "Browse", "Choose a folder")
        self.browse_button.clicked.connect(self.on_browse)
        self.open_folder_button = icon_button(
            theme.ICON_OPEN, "Open", "Open the folder"
        )
        self.open_folder_button.clicked.connect(self.on_open_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_button)
        folder_row.addWidget(self.open_folder_button)
        column.addLayout(folder_row)

        column.addSpacing(14)
        column.addWidget(rule())
        column.addSpacing(14)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.download_button = action_button("Download", "primary")
        self.download_button.clicked.connect(self.on_download)
        self.cancel_button = action_button("Cancel", "danger")
        self.cancel_button.clicked.connect(self.on_cancel)
        action_row.addWidget(self.download_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        column.addLayout(action_row)

        column.addSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        # The numbers live in the status line below, in monospace.
        self.progress_bar.setTextVisible(False)
        column.addWidget(self.progress_bar)

        column.addSpacing(8)
        self.status_label = QLabel("ready")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        column.addWidget(self.status_label)

        column.addSpacing(14)
        column.addWidget(section_label("Log"))
        column.addSpacing(6)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        column.addWidget(self.log_view, 1)

        self._page = page
        return page

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        if not self._titlebar_done:
            self._titlebar_done = True
            theme.dark_titlebar(self)

    # ------------------------------------------------------------- utilities

    def log(self, message: str, tag: str = "log") -> None:
        """Append one line: a fixed-width tag, then the fact."""
        colour = LOG_TONES.get(tag, theme.MUTED)
        # Escaped first, then the tag's padding is made non-breaking so the
        # column survives HTML whitespace collapsing.
        padded = html.escape(tag[:LOG_TAG_WIDTH].ljust(LOG_TAG_WIDTH))
        padded = padded.replace(" ", "&#160;")
        self.log_view.appendHtml(
            f'<span style="color:{colour};">{padded}</span>'
            f'<span style="color:{theme.TEXT_2};">{html.escape(message)}</span>'
        )

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def set_tab_title(self, title: str) -> None:
        metrics = QFontMetrics(self.tab_label.font())
        room = TAB_MAX_WIDTH - TAB_PADDING
        elided = metrics.elidedText(title, Qt.TextElideMode.ElideRight, room)
        self.tab_label.setText(elided)
        self.tab_label.setToolTip(title if elided != title else "")

    def _dialog(
        self,
        tone: str,
        heading: str,
        message: str,
        buttons: list[tuple[str, str]],
        escape_index: int = 0,
    ) -> int:
        """A modal panel over the page. Blocks until a button is pressed."""
        dialog = BlockDialog(self._page, tone, heading, message, buttons, escape_index)
        result = dialog.exec(freeze=(self._toolbar,))
        # Worker signals can land while the dialog holds a nested event loop,
        # so re-derive every enabled state once it closes.
        self._update_buttons()
        return result

    def _notice(self, tone: str, heading: str, message: str) -> None:
        self._dialog(tone, heading, message, [("Dismiss", "")])

    def _busy(self) -> bool:
        return self._download_worker is not None or self._probe_worker is not None

    def _update_buttons(self) -> None:
        downloading = self._download_worker is not None
        probing = self._probe_worker is not None
        busy = self._busy()

        self.omnibox.setEnabled(not busy)
        self.fetch_button.setEnabled(not busy and bool(self.url_edit.text().strip()))
        self.quality_select.setEnabled(not busy and bool(self._presets))
        self.browse_button.setEnabled(not downloading)
        self.download_button.setEnabled(
            not busy and bool(self._presets) and bool(self.folder_edit.text())
        )
        self.cancel_button.setEnabled(downloading)
        self.open_folder_button.setEnabled(bool(self.folder_edit.text()))
        self.fetch_button.setText("Fetching" if probing else "Fetch")

    def _restore_output_dir(self) -> None:
        saved = self._settings.value("output_dir", "", type=str)
        if saved and os.path.isdir(saved):
            self._set_output_dir(saved)
            return
        downloads = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if downloads and os.path.isdir(downloads):
            self._set_output_dir(downloads)

    def _set_output_dir(self, path: str) -> None:
        # Qt hands back forward slashes; a path is technical text and should
        # read the way Windows writes it.
        self.folder_edit.setText(os.path.normpath(path))
        # Long paths otherwise show their tail; the drive matters more.
        self.folder_edit.setCursorPosition(0)

    def _check_ffmpeg(self) -> None:
        if find_ffmpeg():
            return
        self.log("ffmpeg not found - merging and mp3 conversion will fail", "warn")

    # -------------------------------------------------------------- handlers

    def on_url_changed(self) -> None:
        # Any edit invalidates the fetched quality list.
        if self.url_edit.text().strip() != self._probed_url:
            self._presets = []
            self.quality_select.clear()
            self.detail_label.setVisible(False)
            self.set_tab_title(NEW_TAB)
        self._update_buttons()

    def on_browse(self) -> None:
        start = self.folder_edit.text() or ""
        chosen = QFileDialog.getExistingDirectory(self, "Choose a folder to save into", start)
        if chosen:
            self._set_output_dir(chosen)
            self._settings.setValue("output_dir", chosen)
            self._update_buttons()

    def on_open_folder(self) -> None:
        folder = self.folder_edit.text()
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def on_fetch(self) -> None:
        if self._busy():
            return
        url = self.url_edit.text().strip()
        if not url:
            return

        self.progress_bar.setValue(0)
        self.set_status("reading link")
        self.log(url, "read")

        self._probe_worker = ProbeWorker(url, self)
        self._probe_worker.succeeded.connect(self.on_probe_ok)
        self._probe_worker.failed.connect(self.on_probe_failed)
        self._probe_worker.finished.connect(self.on_probe_finished)
        self._probe_worker.start()
        self._update_buttons()

    def on_probe_ok(self, info) -> None:
        self._presets = list(info.presets)
        self._probed_url = self.url_edit.text().strip()

        self.quality_select.set_items([preset.label for preset in self._presets])

        # The title names the tab, the way a page title does.
        self.set_tab_title(info.title)
        detail = info.duration
        if info.uploader:
            detail = f"{detail}  ·  {info.uploader}"
        self.detail_label.setText(detail)
        self.detail_label.setVisible(True)

        self.set_status("ready to download")
        self.log(f"{len(self._presets)} qualities", "ok")

    def on_probe_failed(self, message: str) -> None:
        self.set_status("link unreadable")
        self.log(message, "error")
        self._notice("warning", "link", message)

    def on_probe_finished(self) -> None:
        self._probe_worker = None
        self._update_buttons()

    def on_download(self) -> None:
        if self._busy():
            return

        index = self.quality_select.current_index()
        if not self._presets or index < 0 or index >= len(self._presets):
            return

        folder = self.folder_edit.text()
        if not folder or not os.path.isdir(folder):
            self._notice("warning", "no folder", "Choose a folder to save into first.")
            return

        preset = self._presets[index]
        url = self._probed_url or self.url_edit.text().strip()

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_status("starting")
        self.log(preset.label, "get")

        self._download_worker = DownloadWorker(url, preset, folder, self)
        self._download_worker.progress.connect(self.on_progress)
        self._download_worker.log.connect(self.on_worker_log)
        self._download_worker.succeeded.connect(self.on_download_ok)
        self._download_worker.failed.connect(self.on_download_failed)
        self._download_worker.cancelled.connect(self.on_download_cancelled)
        self._download_worker.finished.connect(self.on_download_finished)
        self._download_worker.start()
        self._update_buttons()

    def on_worker_log(self, message: str) -> None:
        self.log(message, "ffmpeg")

    def on_progress(self, percent: int, detail: str) -> None:
        if percent < 0:
            # Size unknown - show a busy indicator rather than a fake number.
            self.progress_bar.setRange(0, 0)
            self.set_status(detail)
            return
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self.set_status(f"{percent:>3}%  {detail}")

    def on_download_ok(self, path: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        if path:
            self.set_status(f"done  ·  {os.path.basename(path)}")
            self.log(path, "save")
        else:
            self.set_status("done")

    def on_download_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_status("failed")
        self.log(message, "error")
        self._notice("danger", "download failed", message)

    def on_download_cancelled(self) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_status("cancelled")
        self.log("partial files removed", "cancel")

    def on_download_finished(self) -> None:
        self._download_worker = None
        self._update_buttons()

    def on_cancel(self) -> None:
        if self._download_worker is None:
            return
        self.set_status("cancelling")
        self.cancel_button.setEnabled(False)
        self._download_worker.cancel()

    # ---------------------------------------------------------------- closing

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._download_worker is not None:
            answer = self._dialog(
                "ask",
                "download running",
                "A download is still running. Cancel it and quit?",
                [("Keep downloading", "primary"), ("Quit", "danger")],
                escape_index=0,
            )
            if answer != 1:
                event.ignore()
                return
            self._download_worker.cancel()
            self._download_worker.wait(5000)

        if self._probe_worker is not None:
            self._probe_worker.wait(2000)

        event.accept()
