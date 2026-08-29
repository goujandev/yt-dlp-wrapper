"""The GrabIt main window.

The window owns the widgets and the two workers; all blocking work lives in
worker.py, so every method here returns immediately.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QSettings, QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, ORG_NAME, __version__
from .ffmpeg_tools import find_ffmpeg
from .resources import WINDOW_ICON, resource_path
from .worker import DownloadWorker, ProbeWorker


def app_icon() -> QIcon:
    """The GrabIt icon, or an empty icon if the asset is missing."""
    path = resource_path(WINDOW_ICON)
    return QIcon(path) if path else QIcon()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(620, 520)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._probe_worker: ProbeWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._presets: list = []
        self._probed_url = ""

        self._build_ui()
        self._restore_output_dir()
        self._check_ffmpeg()
        self._update_buttons()

    # ---------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        # URL
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a video link, then press Enter")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.returnPressed.connect(self.on_fetch)
        self.url_edit.textChanged.connect(self.on_url_changed)
        self.fetch_button = QPushButton("Fetch qualities")
        self.fetch_button.clicked.connect(self.on_fetch)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.fetch_button)
        form.addRow("Video link", url_row)

        # Quality
        self.quality_combo = QComboBox()
        self.quality_combo.setEnabled(False)
        self.quality_combo.addItem("Fetch a link first")
        form.addRow("Quality", self.quality_combo)

        # Output folder
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.on_browse)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.browse_button)
        form.addRow("Save to", folder_row)

        outer.addLayout(form)

        # Video title / metadata, shown once a link is fetched.
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.TextFormat.PlainText)
        outer.addWidget(self.info_label)

        # Actions
        button_row = QHBoxLayout()
        self.download_button = QPushButton("Download")
        self.download_button.setDefault(True)
        self.download_button.clicked.connect(self.on_download)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.on_cancel)
        self.open_folder_button = QPushButton("Open folder")
        self.open_folder_button.clicked.connect(self.on_open_folder)
        button_row.addWidget(self.download_button)
        button_row.addWidget(self.cancel_button)
        button_row.addStretch(1)
        button_row.addWidget(self.open_folder_button)
        outer.addLayout(button_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        outer.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        outer.addWidget(self.log_view, 1)

        self.setCentralWidget(central)

    # ------------------------------------------------------------- utilities

    def log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _busy(self) -> bool:
        return self._download_worker is not None or self._probe_worker is not None

    def _update_buttons(self) -> None:
        downloading = self._download_worker is not None
        probing = self._probe_worker is not None

        self.url_edit.setEnabled(not self._busy())
        self.fetch_button.setEnabled(not self._busy() and bool(self.url_edit.text().strip()))
        self.quality_combo.setEnabled(not self._busy() and bool(self._presets))
        self.browse_button.setEnabled(not downloading)
        self.download_button.setEnabled(
            not self._busy() and bool(self._presets) and bool(self.folder_edit.text())
        )
        self.cancel_button.setEnabled(downloading)
        self.open_folder_button.setEnabled(bool(self.folder_edit.text()))
        self.fetch_button.setText("Fetching..." if probing else "Fetch qualities")

    def _restore_output_dir(self) -> None:
        saved = self._settings.value("output_dir", "", type=str)
        if saved and os.path.isdir(saved):
            self.folder_edit.setText(saved)
            return
        downloads = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if downloads and os.path.isdir(downloads):
            self.folder_edit.setText(downloads)

    def _check_ffmpeg(self) -> None:
        if find_ffmpeg():
            return
        self.log(
            "Warning: ffmpeg was not found. High-quality downloads and MP3 "
            "conversion need it, and will fail until it is available."
        )

    # -------------------------------------------------------------- handlers

    def on_url_changed(self) -> None:
        # Any edit invalidates the fetched quality list.
        if self.url_edit.text().strip() != self._probed_url:
            self._presets = []
            self.quality_combo.clear()
            self.quality_combo.addItem("Fetch a link first")
            self.info_label.setText("")
        self._update_buttons()

    def on_browse(self) -> None:
        start = self.folder_edit.text() or ""
        chosen = QFileDialog.getExistingDirectory(self, "Choose a folder to save into", start)
        if chosen:
            self.folder_edit.setText(chosen)
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
        self.set_status("Fetching available qualities...")
        self.log(f"Reading {url}")

        self._probe_worker = ProbeWorker(url, self)
        self._probe_worker.succeeded.connect(self.on_probe_ok)
        self._probe_worker.failed.connect(self.on_probe_failed)
        self._probe_worker.finished.connect(self.on_probe_finished)
        self._probe_worker.start()
        self._update_buttons()

    def on_probe_ok(self, info) -> None:
        self._presets = list(info.presets)
        self._probed_url = self.url_edit.text().strip()

        self.quality_combo.clear()
        for preset in self._presets:
            self.quality_combo.addItem(preset.label)
        self.quality_combo.setCurrentIndex(0)

        who = f" - {info.uploader}" if info.uploader else ""
        self.info_label.setText(f"{info.title}  ({info.duration}){who}")
        self.set_status("Ready to download.")
        self.log(f"Found {len(self._presets)} quality options.")

    def on_probe_failed(self, message: str) -> None:
        self.set_status("Could not read that link.")
        self.log(f"Error: {message}")
        QMessageBox.warning(self, APP_NAME, message)

    def on_probe_finished(self) -> None:
        self._probe_worker = None
        self._update_buttons()

    def on_download(self) -> None:
        if self._busy():
            return

        index = self.quality_combo.currentIndex()
        if not self._presets or index < 0 or index >= len(self._presets):
            return

        folder = self.folder_edit.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, APP_NAME, "Choose a folder to save into first.")
            return

        preset = self._presets[index]
        url = self._probed_url or self.url_edit.text().strip()

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_status("Starting download...")
        self.log(f"Downloading: {preset.label}")

        self._download_worker = DownloadWorker(url, preset, folder, self)
        self._download_worker.progress.connect(self.on_progress)
        self._download_worker.log.connect(self.log)
        self._download_worker.succeeded.connect(self.on_download_ok)
        self._download_worker.failed.connect(self.on_download_failed)
        self._download_worker.cancelled.connect(self.on_download_cancelled)
        self._download_worker.finished.connect(self.on_download_finished)
        self._download_worker.start()
        self._update_buttons()

    def on_progress(self, percent: int, detail: str) -> None:
        if percent < 0:
            # Size unknown - show a busy indicator rather than a fake number.
            self.progress_bar.setRange(0, 0)
        else:
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
        self.set_status(detail)

    def on_download_ok(self, path: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        if path:
            self.set_status(f"Done: {os.path.basename(path)}")
            self.log(f"Saved to {path}")
        else:
            self.set_status("Done.")
            self.log("Download finished.")

    def on_download_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_status("Download failed.")
        self.log(f"Error: {message}")
        QMessageBox.critical(self, APP_NAME, message)

    def on_download_cancelled(self) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_status("Cancelled.")
        self.log("Download cancelled; partial files removed.")

    def on_download_finished(self) -> None:
        self._download_worker = None
        self._update_buttons()

    def on_cancel(self) -> None:
        if self._download_worker is None:
            return
        self.set_status("Cancelling...")
        self.cancel_button.setEnabled(False)
        self._download_worker.cancel()

    # ---------------------------------------------------------------- closing

    def closeEvent(self, event) -> None:
        if self._download_worker is not None:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "A download is still running. Cancel it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._download_worker.cancel()
            self._download_worker.wait(5000)

        if self._probe_worker is not None:
            self._probe_worker.wait(2000)

        event.accept()
