"""The GrabIt look: a flat, zero-radius dark theme in the Arch Linux palette.

Everything visual lives here - colours, the three type roles, and the global
stylesheet - so the widget code in ui.py stays about behaviour. Surfaces are
separated by 1px hairlines rather than elevation; nothing is rounded, and the
one accent colour is spent only on state.
"""

from __future__ import annotations

import os
from string import Template

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette

# ------------------------------------------------------------------- palette

STRIP = "#08090B"        # deepest strip: the tab bar
BASE = "#0C0E10"         # page background, recessed inputs
SURFACE = "#121517"      # toolbar and panels
RAISED = "#16191C"       # cards, active rows
HOVER = "#1C2126"
PRESSED = "#22282E"
LINE = "#23292F"         # hairline
LINE_STRONG = "#2E353C"  # border for things you can click

TEXT = "#DCE1E6"
TEXT_2 = "#AEB7C0"
MUTED = "#828C96"

ACCENT = "#1793D1"       # Arch blue - state only, never decoration
ACCENT_DEEP = "#0E5F88"  # filled buttons
ACCENT_LIT = "#1477A6"   # primary button hover, between the two

WARNING = "#D99A4E"
DANGER = "#D9534F"

# --------------------------------------------------------------------- fonts

_UI_STACK = ("Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans")
_MONO_STACK = ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New")
# Line-weight icon fonts that ship with Windows: the first with Windows 11, the
# second with Windows 10. Neither exists elsewhere, so icons stay optional.
_ICON_STACK = ("Segoe Fluent Icons", "Segoe MDL2 Assets")

UI_FONT = _UI_STACK[0]
MONO_FONT = _MONO_STACK[0]
ICON_FONT: str | None = None

# Icon-font glyphs, shared by both Segoe icon fonts. Spelled as code points
# because they live in the private use area, where a literal is unreadable in
# an editor and fragile across encodings.
ICON_LINK = chr(0xE71B)          # link
ICON_FOLDER = chr(0xE8B7)        # folder
ICON_OPEN = chr(0xE8A7)          # open in a new window
ICON_CHEVRON = chr(0xE70D)       # chevron down
ICON_DONE = chr(0xE73E)          # check mark

UI_SIZE = 13
MONO_SIZE = 12
LABEL_SIZE = 11
ROW_HEIGHT = 32


def _first_available(candidates: tuple[str, ...], families: set[str]) -> str | None:
    for name in candidates:
        if name in families:
            return name
    return None


def _resolve_fonts() -> None:
    """Pick the best font installed for each of the three type roles."""
    global UI_FONT, MONO_FONT, ICON_FONT
    families = set(QFontDatabase.families())
    UI_FONT = _first_available(_UI_STACK, families) or QFont().defaultFamily()
    MONO_FONT = (
        _first_available(_MONO_STACK, families)
        or QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    )
    ICON_FONT = _first_available(_ICON_STACK, families)


def has_icons() -> bool:
    """True when an icon font is installed; icons are dropped entirely if not."""
    return ICON_FONT is not None


def label_font() -> QFont:
    """UPPERCASE monospace with generous letter-spacing, for section labels.

    Qt style sheets have no letter-spacing property, so it is set on the font.
    """
    font = QFont(MONO_FONT)
    font.setPixelSize(LABEL_SIZE)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
    return font


# ---------------------------------------------------------------- stylesheet

# $-substitution rather than str.format, because QSS is full of braces.
_QSS = Template("""
/* Nothing is rounded, anywhere. */
* { border-radius: 0px; }

QWidget {
    background-color: $base;
    color: $text;
    font-family: "$ui";
    font-size: ${ui_size}px;
}

/* ---------------------------------------------------------------- tab strip */
QWidget#strip { background-color: $strip; }

/* The active tab takes the toolbar's exact colour so the two read as one
   continuous surface, and carries a 2px accent rule along its top edge. */
QLabel#tab {
    background-color: $surface;
    color: $text;
    border-top: 2px solid $accent;
    padding: 0px 14px;
    font-size: 12px;
}
QLabel#version {
    background-color: $strip;
    color: $muted;
    font-family: "$mono";
    font-size: ${label_size}px;
    padding: 0px 12px;
}

/* ------------------------------------------------------------------ toolbar */
QWidget#toolbar {
    background-color: $surface;
    border-bottom: 1px solid $line;
}
QLabel#detailText {
    background-color: $surface;
    color: $muted;
    font-family: "$mono";
    font-size: ${mono_size}px;
}

/* Recessed: darker than the surface it sits in, accent border on focus. */
QFrame#omnibox {
    background-color: $base;
    border: 1px solid $strong;
}
QFrame#omnibox[focused="true"] { border: 1px solid $accent; }
QFrame#omnibox:disabled { border: 1px solid $line; }
QFrame#omnibox QLineEdit {
    background-color: transparent;
    border: 0px;
    color: $text;
    font-family: "$mono";
    font-size: ${ui_size}px;
    padding: 0px 8px 0px 0px;
}
QFrame#omnibox QLineEdit:disabled { color: $muted; }
QLabel#omniIcon {
    background-color: transparent;
    color: $muted;
    font-family: "$icon";
    font-size: 14px;
    padding: 0px 8px;
}

/* ------------------------------------------------------------------ buttons */
QPushButton {
    background-color: $raised;
    color: $text;
    border: 1px solid $strong;
    padding: 0px 14px;
    font-size: ${ui_size}px;
}
QPushButton:hover { background-color: $hover; }
QPushButton:pressed { background-color: $pressed; }
QPushButton:disabled {
    background-color: $surface;
    color: $muted;
    border: 1px solid $line;
}
QPushButton#primary {
    background-color: $accent_deep;
    border: 1px solid $accent;
    color: $text;
}
QPushButton#primary:hover { background-color: $accent_lit; }
QPushButton#primary:pressed { background-color: $accent_deep; }
QPushButton#primary:disabled {
    background-color: $surface;
    color: $muted;
    border: 1px solid $line;
}
QPushButton#danger { color: $danger; }
QPushButton#danger:disabled { color: $muted; }
QPushButton#icon {
    font-family: "$icon";
    font-size: 15px;
    padding: 0px;
}

/* ------------------------------------------------------------------- labels */
QLabel#section { background-color: transparent; color: $muted; }
QLabel#status {
    background-color: transparent;
    color: $text_2;
    font-family: "$mono";
    font-size: ${mono_size}px;
}

/* ------------------------------------------------------------ input surfaces */
QLineEdit#field {
    background-color: $base;
    border: 1px solid $line;
    color: $text_2;
    font-family: "$mono";
    font-size: ${mono_size}px;
    padding: 0px 8px;
}
QPlainTextEdit#log {
    background-color: $base;
    border: 1px solid $line;
    color: $text_2;
    font-family: "$mono";
    font-size: ${mono_size}px;
    padding: 6px 8px;
}

/* ------------------------------------------------------------------- select */
QFrame#select {
    background-color: $base;
    border: 1px solid $strong;
}
QFrame#select[open="true"] { border: 1px solid $accent; }
QFrame#select:disabled { border: 1px solid $line; }
QLabel#selectText {
    background-color: transparent;
    color: $text;
    padding-left: 8px;
}
QLabel#selectText:disabled { color: $muted; }
QLabel#selectChevron {
    background-color: transparent;
    color: $muted;
    font-family: "$icon";
    font-size: 12px;
    padding-right: 8px;
}

/* Menus are built from our own rows and drawn inside the window. */
QFrame#popup {
    background-color: $surface;
    border: 1px solid $strong;
}
QPushButton#row {
    background-color: $surface;
    color: $text_2;
    border: 0px;
    border-left: 2px solid transparent;
    text-align: left;
    padding: 0px 12px;
    font-size: ${ui_size}px;
}
QPushButton#row:hover { background-color: $hover; color: $text; }
QPushButton#row[selected="true"] {
    background-color: $raised;
    border-left: 2px solid $accent;
    color: $text;
}

/* ------------------------------------------------------------------ progress */
QProgressBar {
    background-color: $base;
    border: 1px solid $line;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk { background-color: $accent; }

/* The finished download. Takes the progress bar's place rather than sitting
   beside it, so only one of the two is ever on screen and the accent does not
   end up spent twice on the same state. */
QFrame#result {
    background-color: $raised;
    border: 1px solid $line;
    border-left: 2px solid $accent;
}
QLabel#resultIcon {
    background-color: transparent;
    color: $text;
    font-family: "$icon";
    font-size: 14px;
    padding: 0px 10px;
}
QLabel#resultName {
    background-color: transparent;
    color: $text;
    font-family: "$mono";
    font-size: ${mono_size}px;
}
QLabel#resultSize {
    background-color: transparent;
    color: $muted;
    font-family: "$mono";
    font-size: ${mono_size}px;
    padding: 0px 12px;
}
QPushButton#reveal {
    background-color: $surface;
    border: 1px solid $strong;
    color: $text_2;
    padding: 0px 12px;
    font-size: 12px;
}
QPushButton#reveal:hover { background-color: $hover; color: $text; }
QPushButton#reveal:pressed { background-color: $pressed; }

/* --------------------------------------------------------------------- rules */
QFrame#rule {
    background-color: $line;
    border: 0px;
    min-height: 1px;
    max-height: 1px;
}

/* -------------------------------------------------------------------- dialog */
QWidget#overlay { background-color: $base; }
QFrame#dialog {
    background-color: $surface;
    border: 1px solid $strong;
}
QFrame#dialog[tone="danger"] {
    border: 1px solid $strong;
    border-top: 2px solid $danger;
}
QFrame#dialog[tone="warning"] {
    border: 1px solid $strong;
    border-top: 2px solid $warning;
}
/* A question carries no semantic colour, and its primary button is already
   spending the accent, so this rule stays neutral. */
QFrame#dialog[tone="ask"] {
    border: 1px solid $strong;
    border-top: 2px solid $strong;
}
QLabel#dialogText {
    background-color: transparent;
    color: $text;
    font-size: ${ui_size}px;
}

/* ---------------------------------------------------------------- scrollbars */
QScrollBar:vertical {
    background-color: $base;
    width: 12px;
    border-left: 1px solid $line;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: $strong;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background-color: #3A424A; }
QScrollBar:horizontal {
    background-color: $base;
    height: 12px;
    border-top: 1px solid $line;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: $strong;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover { background-color: #3A424A; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background-color: transparent; }

QToolTip {
    background-color: $surface;
    color: $text_2;
    border: 1px solid $strong;
    padding: 4px 8px;
    font-size: ${mono_size}px;
}
""")


def stylesheet() -> str:
    return _QSS.substitute(
        strip=STRIP,
        base=BASE,
        surface=SURFACE,
        raised=RAISED,
        hover=HOVER,
        pressed=PRESSED,
        line=LINE,
        strong=LINE_STRONG,
        text=TEXT,
        text_2=TEXT_2,
        muted=MUTED,
        accent=ACCENT,
        accent_deep=ACCENT_DEEP,
        accent_lit=ACCENT_LIT,
        warning=WARNING,
        danger=DANGER,
        ui=UI_FONT,
        mono=MONO_FONT,
        # Falls back to the UI font so a missing icon font degrades to blank
        # rather than to boxes; callers also check has_icons() first.
        icon=ICON_FONT or UI_FONT,
        ui_size=UI_SIZE,
        mono_size=MONO_SIZE,
        label_size=LABEL_SIZE,
    )


def _palette() -> QPalette:
    """QPalette for the parts Qt draws itself: carets, selections, disabled text."""
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: BASE,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: BASE,
        QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Button: RAISED,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.ToolTipBase: SURFACE,
        QPalette.ColorRole.ToolTipText: TEXT_2,
        QPalette.ColorRole.Highlight: ACCENT_DEEP,
        QPalette.ColorRole.HighlightedText: TEXT,
        QPalette.ColorRole.Link: ACCENT,
    }
    for role, colour in roles.items():
        pal.setColor(role, QColor(colour))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(MUTED))
    return pal


def apply(app) -> None:
    """Point a QApplication at the theme. Call once, before the window is built."""
    _resolve_fonts()
    app.setStyle("Fusion")
    app.setPalette(_palette())

    font = QFont(UI_FONT)
    font.setPixelSize(UI_SIZE)
    app.setFont(font)

    app.setStyleSheet(stylesheet())


def dark_titlebar(widget) -> None:
    """Ask Windows for a dark title bar, so the frame matches the tab strip."""
    if os.name != "nt":
        return
    try:
        import ctypes

        handle = ctypes.c_void_p(int(widget.winId()))
        enabled = ctypes.c_int(1)
        # 20 on Windows 10 2004+ and Windows 11; 19 on earlier builds.
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                handle,
                ctypes.c_int(attribute),
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                return
    except Exception:  # noqa: BLE001 - cosmetic only, never worth failing over
        pass
