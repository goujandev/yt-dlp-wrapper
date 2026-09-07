"""The pieces Qt does not provide in this style.

Two of these exist only because the style forbids floating system windows: the
quality dropdown is built from our own rows, and message boxes are a panel drawn
over the page rather than a QMessageBox. Both stay inside the main window.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QEventLoop, QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme

POPUP_ROW_HEIGHT = 30

# The dialog panel. Fixed rather than proportional, and comfortably inside the
# window's 640px minimum width.
PANEL_WIDTH = 420
PANEL_INSET = 34  # the panel's own padding and border, both sides


def repolish(widget: QWidget) -> None:
    """Re-evaluate style sheet rules after a dynamic property has changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def section_label(text: str) -> QLabel:
    """UPPERCASE monospace, muted, generously letter-spaced."""
    label = QLabel(text.upper())
    label.setObjectName("section")
    label.setFont(theme.label_font())
    return label


def rule() -> QFrame:
    """A 1px hairline divider - the way groups are separated here."""
    line = QFrame()
    line.setObjectName("rule")
    line.setFixedHeight(1)
    return line


def icon_label(glyph: str, name: str) -> QLabel:
    """A standalone glyph. Renders as nothing when no icon font is installed."""
    label = QLabel(glyph if theme.has_icons() else "")
    label.setObjectName(name)
    return label


def icon_button(glyph: str, text: str, tooltip: str) -> QPushButton:
    """An icon-only button, falling back to a text button without an icon font."""
    if theme.has_icons():
        button = QPushButton(glyph)
        button.setObjectName("icon")
        button.setFixedSize(theme.ROW_HEIGHT, theme.ROW_HEIGHT)
    else:
        button = QPushButton(text)
        button.setFixedHeight(theme.ROW_HEIGHT)
    button.setToolTip(tooltip)
    return button


def action_button(text: str, kind: str = "") -> QPushButton:
    """A text button. kind is "primary" or "danger", or empty for a plain one."""
    button = QPushButton(text)
    if kind:
        button.setObjectName(kind)
    button.setFixedHeight(theme.ROW_HEIGHT)
    return button


class ElidedLabel(QLabel):
    """A label that shrinks its text to fit rather than widening its row.

    Elides in the middle, because the end of a file name carries the extension.
    """

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(name)
        self._full = ""
        # Ignored, so a long name never pushes the row wider than the window.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        room = max(0, self.width() - 2)
        self.setText(
            self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, room)
        )


class Omnibox(QFrame):
    """The URL field: recessed, monospace, accent border only while focused."""

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("omnibox")
        self.setFixedHeight(theme.ROW_HEIGHT)
        self.setProperty("focused", False)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFrame(False)
        self.edit.installEventFilter(self)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(icon_label(theme.ICON_LINK, "omniIcon"))
        row.addWidget(self.edit, 1)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if obj is self.edit and event.type() in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            self.setProperty("focused", event.type() == QEvent.Type.FocusIn)
            repolish(self)
        return super().eventFilter(obj, event)


class BlockSelect(QFrame):
    """A dropdown whose menu is our own rows, drawn inside the window.

    The platform combo box popup is a floating window with its own frame and
    shadow, which this style does not allow, so the popup here is a plain child
    widget of the main window raised over the page.
    """

    currentIndexChanged = pyqtSignal(int)  # noqa: N815 - mirrors QComboBox

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("select")
        self.setFixedHeight(theme.ROW_HEIGHT)
        self.setProperty("open", False)

        self._placeholder = placeholder
        self._items: list[str] = []
        self._index = -1
        self._popup: QFrame | None = None

        self._text = QLabel(placeholder)
        self._text.setObjectName("selectText")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._text, 1)
        row.addWidget(icon_label(theme.ICON_CHEVRON, "selectChevron"))

    # ------------------------------------------------------------------ model

    def set_items(self, items: list[str]) -> None:
        self.close_popup()
        self._items = list(items)
        self._index = 0 if self._items else -1
        self._text.setText(self._items[0] if self._items else self._placeholder)

    def clear(self) -> None:
        self.set_items([])

    def current_index(self) -> int:
        return self._index

    def count(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------ popup

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._items:
            if self._popup is not None:
                self.close_popup()
            else:
                self.open_popup()
            # Must be accepted. An ignored press is re-sent to the parent, and
            # that second delivery reaches the filter this press just installed,
            # which would read it as a click outside and shut the menu again.
            event.accept()
            return
        super().mousePressEvent(event)

    def open_popup(self) -> None:
        host = self.window()
        popup = QFrame(host)
        popup.setObjectName("popup")

        column = QVBoxLayout(popup)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        for index, label in enumerate(self._items):
            row = QPushButton(label, popup)
            row.setObjectName("row")
            row.setFixedHeight(POPUP_ROW_HEIGHT)
            # The selected row takes a raised fill and a 2px accent left rule.
            row.setProperty("selected", index == self._index)
            row.clicked.connect(lambda _checked=False, i=index: self._choose(i))
            column.addWidget(row)

        popup.adjustSize()
        width = max(self.width(), popup.sizeHint().width())
        height = popup.sizeHint().height()

        anchor = self.mapTo(host, QPoint(0, self.height()))
        top = anchor.y()
        if top + height > host.height():
            # Not enough room below: open upwards, or pin to the window edge.
            above = self.mapTo(host, QPoint(0, 0)).y() - height
            top = above if above >= 0 else max(0, host.height() - height)
        popup.setGeometry(anchor.x(), top, width, height)
        popup.show()
        popup.raise_()

        self._popup = popup
        self.setProperty("open", True)
        repolish(self)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def close_popup(self) -> None:
        if self._popup is None:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._popup.hide()
        self._popup.deleteLater()
        self._popup = None
        self.setProperty("open", False)
        repolish(self)

    def _choose(self, index: int) -> None:
        self.close_popup()
        if not 0 <= index < len(self._items) or index == self._index:
            return
        self._index = index
        self._text.setText(self._items[index])
        self.currentIndexChanged.emit(index)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if self._popup is not None:
            kind = event.type()
            # Only widget presses count. The same press also reaches the QWindow,
            # and closing on that would destroy the row before it is clicked.
            if kind == QEvent.Type.MouseButtonPress and isinstance(obj, QWidget):
                inside = (
                    obj is self._popup
                    or self._popup.isAncestorOf(obj)
                    or obj is self
                    or self.isAncestorOf(obj)
                )
                if not inside:
                    self.close_popup()
            elif kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.close_popup()
                return True
            elif kind == QEvent.Type.Resize and obj is self.window():
                # The popup is positioned absolutely; a resize would strand it.
                self.close_popup()
            elif kind == QEvent.Type.WindowDeactivate:
                self.close_popup()
        return super().eventFilter(obj, event)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.close_popup()
        super().hideEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.type() == QEvent.Type.EnabledChange and not self.isEnabled():
            self.close_popup()
        super().changeEvent(event)


class BlockDialog(QWidget):
    """A modal panel drawn over the page, in place of QMessageBox.

    It fills the page area opaquely and freezes the widgets around it, so the
    tab strip and toolbar stay visible but nothing behind it is reachable.
    """

    def __init__(
        self,
        page: QWidget,
        tone: str,
        heading: str,
        message: str,
        buttons: list[tuple[str, str]],
        escape_index: int = 0,
    ) -> None:
        super().__init__(page)
        self.setObjectName("overlay")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # A QWidget subclass ignores its style sheet background unless told to
        # draw one, and without it the page shows through the overlay.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._result = escape_index
        self._escape_index = escape_index
        self._loop: QEventLoop | None = None
        self._frozen: list[QWidget] = []
        self._default: QPushButton | None = None

        panel = QFrame(self)
        panel.setObjectName("dialog")
        panel.setProperty("tone", tone)
        # A fixed width, not a maximum: a wrapped label only reports the height
        # it needs once the width it must wrap to is settled, and a panel sized
        # from an unwrapped hint clips its own message.
        panel.setFixedWidth(PANEL_WIDTH)

        column = QVBoxLayout(panel)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(12)
        column.addWidget(section_label(heading))

        text = QLabel(message)
        text.setObjectName("dialogText")
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.PlainText)
        # A centred layout item is handed its size hint and never asked to
        # resolve height-for-width, so the wrapped height is measured here.
        inner = PANEL_WIDTH - PANEL_INSET
        text.setFixedWidth(inner)
        text.setFixedHeight(text.heightForWidth(inner))
        column.addWidget(text)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        for index, (label, kind) in enumerate(buttons):
            button = action_button(label, kind)
            button.clicked.connect(lambda _checked=False, i=index: self.finish(i))
            if kind == "primary" or self._default is None:
                self._default = button
            row.addWidget(button)
        column.addLayout(row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(2)
        outer.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)

    def exec(self, freeze: tuple[QWidget, ...] = ()) -> int:
        """Show the dialog and block until a button is pressed."""
        page = self.parentWidget()
        page.installEventFilter(self)
        self.setGeometry(page.rect())

        candidates = [
            child
            for child in page.children()
            if isinstance(child, QWidget) and child is not self
        ]
        candidates.extend(freeze)
        self._frozen = [widget for widget in candidates if widget.isEnabled()]
        for widget in self._frozen:
            widget.setEnabled(False)

        self.show()
        self.raise_()
        if self._default is not None:
            self._default.setFocus()
        else:
            self.setFocus()

        self._loop = QEventLoop()
        self._loop.exec()
        return self._result

    def finish(self, index: int) -> None:
        self._result = index
        page = self.parentWidget()
        if page is not None:
            page.removeEventFilter(self)
        for widget in self._frozen:
            widget.setEnabled(True)
        self._frozen = []
        self.hide()
        if self._loop is not None:
            self._loop.quit()
            self._loop = None
        self.deleteLater()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() == Qt.Key.Key_Escape:
            self.finish(self._escape_index)
            return
        super().keyPressEvent(event)
