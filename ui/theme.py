"""Colors, fonts and the stylesheet (QSS) the whole Qt UI is painted with.

Two palettes live here, dark and light; `MODE` picks one. Either way the
look is the same: a quiet page, cards with a hairline border, and color
only where it means something -- green for money earned and goals met,
red for tip-outs and deletes, one muted blue for projections. Everything
else is grey.

One place for every color and every bit of styling, so screens contain
layout and data only. Widgets opt into a look with a Qt *dynamic property*
rather than their own stylesheet -- e.g. a button with
`variant="primary"` -- because a stylesheet set on a single widget
overrides the app-wide one and makes styling impossible to follow.
"""
import os

from PySide6.QtGui import QFont, QFontDatabase

import charts

# Change this to "light" for the light theme; nothing else needs touching.
MODE = "dark"

PALETTES = {
    "dark": dict(
        BG="#16181a",        # the page
        SURFACE="#1e2125",   # cards, tables, inputs
        HOVER="#272b30",     # hover fill on quiet controls
        BORDER="#2e3338",    # hairlines
        RULE="#262a2e",      # row separators: quieter than BORDER
        TEXT="#eceef0",      # headlines and figures
        BODY="#c3c9ce",      # ordinary text
        MUTED="#868d94",     # captions, secondary figures
        ACCENT="#3ec291",    # money earned, goals met
        INFO="#6aa6e8",      # projections
        WARNING="#dda55c",   # behind on a goal, unlogged shifts
        DANGER="#d9796b",    # tip-outs, delete
        HOLIDAY="#b98cd9",   # holiday greeting (a festive note, dark)
        # Shades that only the stylesheet needs.
        ON_PRIMARY="#16181a",    # text on the one solid button
        PRIMARY_HOVER="#ffffff",
        PRIMARY_OFF="#4a5057",   # that button, disabled
        PRESSED="#2f343a",
        PLACEHOLDER="#6d757c",
        TRACK="#2b3036",         # progress-bar groove
        SCROLL="#3a4046",
        SCROLL_HOVER="#4a5157",
        FOCUS="#4a5a6b",
        SELECT="#2d3b49",        # selected text in an input
        DANGER_WASH="#2a2022",   # hover behind a delete button
        CHART=charts.NIGHT,
    ),
    "light": dict(
        BG="#f5f5f3",
        SURFACE="#ffffff",
        HOVER="#f0f0ec",
        BORDER="#e4e4de",
        RULE="#efefeb",
        TEXT="#23262a",
        BODY="#3f444a",
        MUTED="#80858c",
        ACCENT="#2f8f6b",
        INFO="#4a7db5",
        WARNING="#9a6b1e",
        DANGER="#b5503f",
        HOLIDAY="#8257b5",   # holiday greeting (light)
        ON_PRIMARY="#ffffff",
        PRIMARY_HOVER="#34383d",
        PRIMARY_OFF="#b6babe",
        PRESSED="#e7e7e2",
        PLACEHOLDER="#b2b6ba",
        TRACK="#ebebe6",
        SCROLL="#d2d2cc",
        SCROLL_HOVER="#bcbcb5",
        FOCUS="#b9c6d6",
        SELECT="#d7e3f1",
        DANGER_WASH="#fbf1ef",
        CHART=charts.LIGHT,
    ),
}

# The active palette, as module constants (theme.TEXT, theme.ACCENT, ...).
globals().update(PALETTES[MODE])
CHART = PALETTES[MODE]["CHART"]   # the matplotlib palette that matches

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

FAMILY = "Segoe UI"
SIZES = {"big": 22, "title": 18, "head": 12, "body": 10, "small": 8}


def load_fonts():
    """Register the bundled Inter .ttf files with Qt (no install needed).
    Call once, after QApplication exists. Falls back to Segoe UI."""
    global FAMILY
    for name in ("Inter-Regular.ttf", "Inter-Bold.ttf"):
        path = os.path.join(_FONT_DIR, name)
        if os.path.exists(path):
            fid = QFontDatabase.addApplicationFont(path)
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    FAMILY = families[0]
    return FAMILY


def font(size="body", bold=False):
    f = QFont(FAMILY, SIZES[size])
    f.setBold(bold)
    return f


def stylesheet():
    """The app-wide QSS, filled in from the active palette."""
    values = dict(PALETTES[MODE], FAMILY=FAMILY,
                  S_BIG=SIZES["big"], S_TITLE=SIZES["title"],
                  S_HEAD=SIZES["head"], S_BODY=SIZES["body"],
                  S_SMALL=SIZES["small"])
    values.pop("CHART")
    return _QSS % values


_QSS = """
    QWidget {
        color: %(BODY)s;
        font-family: "%(FAMILY)s";
        font-size: %(S_BODY)dpt;
    }
    /* Only the windows paint the page background. A rule like
       "QWidget { background: ... }" would also repaint the inside of every
       card and button, and a card's ID selector would then outweigh the
       button styles below -- so widgets stay transparent unless they style
       themselves. */
    QMainWindow, QDialog, QMessageBox { background: %(BG)s; }
    QToolTip {
        background: %(SURFACE)s; color: %(TEXT)s;
        border: 1px solid %(BORDER)s; padding: 7px 9px;
    }

    /* --- Cards ------------------------------------------------------- */
    QFrame#card {
        background: %(SURFACE)s;
        border: 1px solid %(BORDER)s;
        border-radius: 14px;
    }
    QFrame#sep { background: %(BORDER)s; border: none; }

    /* --- Text -------------------------------------------------------- */
    QLabel[role="caption"] {
        color: %(MUTED)s; font-size: %(S_SMALL)dpt; letter-spacing: 1.2px;
    }
    QLabel[role="muted"]  { color: %(MUTED)s; }
    QLabel[role="big"]    { color: %(TEXT)s; font-size: %(S_BIG)dpt;
                            font-weight: bold; }
    QLabel[role="title"]  { color: %(TEXT)s; font-size: %(S_TITLE)dpt;
                            font-weight: bold; }
    QLabel[role="head"]   { color: %(TEXT)s; font-size: %(S_HEAD)dpt;
                            font-weight: bold; }
    QLabel[role="figure"] { color: %(TEXT)s; font-size: %(S_HEAD)dpt; }
    QLabel[tone="accent"]  { color: %(ACCENT)s; }
    QLabel[tone="info"]    { color: %(INFO)s; }
    QLabel[tone="warning"] { color: %(WARNING)s; }
    QLabel[tone="danger"]  { color: %(DANGER)s; }
    QLabel[tone="holiday"] { color: %(HOLIDAY)s; font-weight: bold; }

    /* --- Buttons ----------------------------------------------------- */
    /* Quiet by default; one solid button per screen carries the action. */
    QPushButton {
        background: %(SURFACE)s;
        color: %(BODY)s;
        border: 1px solid %(BORDER)s;
        border-radius: 10px;
        padding: 9px 16px;
    }
    QPushButton:hover   { background: %(HOVER)s; color: %(TEXT)s; }
    QPushButton:pressed { background: %(PRESSED)s; }
    QPushButton:disabled { color: %(PLACEHOLDER)s; background: %(SURFACE)s; }
    QPushButton[variant="primary"] {
        background: %(TEXT)s; color: %(ON_PRIMARY)s; border-color: %(TEXT)s;
        font-weight: bold;
    }
    QPushButton[variant="primary"]:hover {
        background: %(PRIMARY_HOVER)s; color: %(ON_PRIMARY)s;
        border-color: %(PRIMARY_HOVER)s;
    }
    QPushButton[variant="primary"]:disabled {
        background: %(PRIMARY_OFF)s; border-color: %(PRIMARY_OFF)s;
        color: %(SURFACE)s;
    }
    QPushButton[variant="day"] {
        padding: 8px 0; min-width: 46px; border-radius: 9px; color: %(MUTED)s;
    }
    QPushButton[variant="day"]:checked {
        background: %(TEXT)s; color: %(ON_PRIMARY)s; border-color: %(TEXT)s;
        font-weight: bold;
    }
    QPushButton[variant="danger"] { color: %(DANGER)s; }
    QPushButton[variant="danger"]:hover { background: %(DANGER_WASH)s; color: %(DANGER)s; }
    QPushButton[variant="ghost"] {
        background: transparent; border-color: transparent; color: %(MUTED)s;
    }
    QPushButton[variant="ghost"]:hover { background: %(HOVER)s; color: %(TEXT)s; }
    QPushButton[variant="link"] {
        background: transparent; border: none; color: %(MUTED)s; padding: 4px;
    }
    QPushButton[variant="link"]:hover { color: %(TEXT)s; }
    /* View Logs' tab strip */
    QPushButton[variant="tab"] {
        background: transparent; border: none; border-bottom: 2px solid transparent;
        border-radius: 0; padding: 7px 2px; margin-right: 22px; color: %(MUTED)s;
    }
    QPushButton[variant="tab"]:hover { color: %(TEXT)s; background: transparent; }
    QPushButton[variant="tab"][active="true"] {
        color: %(TEXT)s; border-bottom: 2px solid %(TEXT)s; font-weight: bold;
    }

    /* --- Inputs ------------------------------------------------------ */
    QLineEdit, QComboBox, QDateEdit, QAbstractSpinBox {
        background: %(SURFACE)s;
        color: %(TEXT)s;
        border: 1px solid %(BORDER)s;
        border-radius: 10px;
        padding: 9px 11px;
        selection-background-color: %(SELECT)s;
        selection-color: %(TEXT)s;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color: %(FOCUS)s; }
    QLineEdit[invalid="true"] { border-color: %(DANGER)s; }
    QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 24px; }
    QComboBox::down-arrow, QDateEdit::down-arrow {
        image: none; width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid %(MUTED)s;
        margin-right: 9px;
    }
    QComboBox QAbstractItemView {
        background: %(SURFACE)s;
        color: %(BODY)s;
        border: 1px solid %(BORDER)s;
        selection-background-color: %(HOVER)s;
        selection-color: %(TEXT)s;
        padding: 4px;
        outline: none;
    }

    /* --- Calendar popup (QDateEdit) ---------------------------------- */
    QCalendarWidget QWidget { background: %(SURFACE)s; }
    QCalendarWidget QAbstractItemView {
        background: %(SURFACE)s;
        color: %(BODY)s;
        selection-background-color: %(TEXT)s;
        selection-color: %(ON_PRIMARY)s;
        outline: none;
    }
    QCalendarWidget QToolButton {
        background: transparent; border: none; color: %(TEXT)s;
        padding: 6px; margin: 2px;
    }
    QCalendarWidget QToolButton:hover { background: %(HOVER)s; border-radius: 8px; }
    QCalendarWidget QMenu, QCalendarWidget QSpinBox { background: %(SURFACE)s; }

    /* --- Tables ------------------------------------------------------ */
    /* No zebra striping and no vertical rules: a hairline under each row is
       enough to read along, and much quieter. */
    QTableView {
        background: %(SURFACE)s;
        border: 1px solid %(BORDER)s;
        border-radius: 12px;
        gridline-color: transparent;
        selection-background-color: %(HOVER)s;
        selection-color: %(TEXT)s;
        outline: none;
        padding: 2px;
    }
    QTableView::item {
        padding: 9px 12px;
        border-bottom: 1px solid %(RULE)s;
        color: %(BODY)s;
    }
    QTableView::item:selected { color: %(TEXT)s; }
    QHeaderView::section {
        background: %(SURFACE)s;
        color: %(MUTED)s;
        border: none;
        border-bottom: 1px solid %(BORDER)s;
        padding: 10px 12px;
        font-size: %(S_SMALL)dpt;
        letter-spacing: 1px;
    }
    QHeaderView::section:hover { color: %(TEXT)s; }
    QTableCornerButton::section { background: %(SURFACE)s; border: none; }

    /* --- Misc -------------------------------------------------------- */
    QProgressBar {
        background: %(TRACK)s; border: none; border-radius: 3px;
        height: 6px; text-align: center; color: transparent;
    }
    QProgressBar::chunk { background: %(ACCENT)s; border-radius: 3px; }
    QProgressBar[tone="muted"]::chunk { background: %(SCROLL)s; }

    QScrollBar:vertical   { background: transparent; width: 10px; margin: 4px; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 4px; }
    QScrollBar::handle {
        background: %(SCROLL)s; border-radius: 5px; min-height: 32px; min-width: 32px;
    }
    QScrollBar::handle:hover { background: %(SCROLL_HOVER)s; }
    QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""
