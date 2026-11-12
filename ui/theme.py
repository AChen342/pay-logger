"""Colors, fonts and the stylesheet (QSS) the whole Qt UI is painted with.

One place for every color and every bit of styling, so screens contain
layout and data only. Widgets opt into a look with a Qt *dynamic property*
rather than their own stylesheet -- e.g. a button with
`variant="success"` turns green -- because a stylesheet set on a single
widget overrides the app-wide one and makes styling impossible to follow.
"""
import os

from PySide6.QtGui import QFont, QFontDatabase

import charts

# Chart colors live in `charts` (it has no Qt in it, so it can't import
# this module); mirror them here so screens have one place to look.
BG = charts.BG            # window background
SURFACE = "#282828"       # cards
SURFACE_HI = "#303030"    # inputs, table headers
BORDER = "#3a3a3a"
TEXT = "#e9ecef"
MUTED = "#8b949e"
ACCENT = charts.CASH      # green: take-home, success
INFO = charts.CARD        # blue: forecasts, neutral emphasis
WARNING = "#f0932b"
DANGER = charts.TIPOUT    # red: tip-out, delete

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

FAMILY = "Segoe UI"
SIZES = {"big": 30, "title": 22, "head": 13, "body": 11, "small": 9}


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
    """The app-wide QSS. `{...}` holes are filled from the colors above."""
    return """
    QWidget {
        color: %(TEXT)s;
        font-family: "%(FAMILY)s";
        font-size: %(BODY)dpt;
    }
    /* Only the windows paint the page background. A rule like
       "QWidget { background: ... }" would also repaint the inside of every
       card and button, and a card's ID selector would then outwrite the
       button styles below -- so widgets stay transparent unless they style
       themselves. */
    QMainWindow, QDialog, QMessageBox { background: %(BG)s; }
    QToolTip {
        background: %(SURFACE_HI)s; color: %(TEXT)s;
        border: 1px solid %(BORDER)s; padding: 6px;
    }

    /* --- Cards: any widget with objectName "card" ------------------- */
    QFrame#card {
        background: %(SURFACE)s;
        border: 1px solid %(BORDER)s;
        border-radius: 12px;
    }
    QFrame#tile {
        background: %(SURFACE)s;
        border: 1px solid %(BORDER)s;
        border-radius: 10px;
    }
    QFrame#sep { background: %(BORDER)s; border: none; }

    QLabel[role="caption"] { color: %(MUTED)s; font-size: %(SMALL)dpt;
                             letter-spacing: 1px; }
    QLabel[role="muted"]   { color: %(MUTED)s; }
    QLabel[role="big"]     { font-size: %(BIG)dpt; font-weight: bold; }
    QLabel[role="title"]   { font-size: %(TITLE)dpt; font-weight: bold; }
    QLabel[role="head"]    { font-size: %(HEAD)dpt; font-weight: bold; }
    QLabel[tone="accent"]  { color: %(ACCENT)s; }
    QLabel[tone="info"]    { color: %(INFO)s; }
    QLabel[tone="warning"] { color: %(WARNING)s; }
    QLabel[tone="danger"]  { color: %(DANGER)s; }

    /* --- Buttons ---------------------------------------------------- */
    QPushButton {
        background: %(SURFACE_HI)s;
        border: 1px solid %(BORDER)s;
        border-radius: 8px;
        padding: 9px 16px;
    }
    QPushButton:hover   { background: #3a3a3a; }
    QPushButton:pressed { background: #434343; }
    QPushButton:disabled { color: #6b6b6b; border-color: #313131; }
    QPushButton[variant="primary"] {
        background: %(INFO)s; border-color: %(INFO)s; color: #10212e;
        font-weight: bold;
    }
    QPushButton[variant="primary"]:hover { background: #5dade2; }
    QPushButton[variant="success"] {
        background: %(ACCENT)s; border-color: %(ACCENT)s; color: #06261d;
        font-weight: bold;
    }
    QPushButton[variant="success"]:hover { background: #2fd3ab; }
    QPushButton[variant="danger"] {
        background: %(DANGER)s; border-color: %(DANGER)s; color: #2c0b07;
        font-weight: bold;
    }
    QPushButton[variant="danger"]:hover { background: #ec7063; }
    QPushButton[variant="ghost"] { background: transparent; }
    QPushButton[variant="ghost"]:hover { background: %(SURFACE_HI)s; }
    QPushButton[variant="link"] {
        background: transparent; border: none; color: %(INFO)s; padding: 4px;
    }
    QPushButton[variant="link"]:hover { color: #7fc4ea; }
    /* View Logs' tab strip */
    QPushButton[variant="tab"] {
        background: transparent; border: none; border-bottom: 2px solid transparent;
        border-radius: 0; padding: 8px 18px; color: %(MUTED)s;
    }
    QPushButton[variant="tab"]:hover { color: %(TEXT)s; }
    QPushButton[variant="tab"][active="true"] {
        color: %(TEXT)s; border-bottom: 2px solid %(INFO)s; font-weight: bold;
    }

    /* --- Inputs ------------------------------------------------------ */
    QLineEdit, QComboBox, QDateEdit, QAbstractSpinBox {
        background: %(SURFACE_HI)s;
        border: 1px solid %(BORDER)s;
        border-radius: 8px;
        padding: 8px 10px;
        selection-background-color: %(INFO)s;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
        border-color: %(INFO)s;
    }
    QLineEdit[invalid="true"] { border-color: %(DANGER)s; }
    QComboBox::drop-down, QDateEdit::drop-down {
        border: none; width: 22px;
    }
    QComboBox::down-arrow, QDateEdit::down-arrow {
        image: none;
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid %(MUTED)s;
        margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background: %(SURFACE_HI)s;
        border: 1px solid %(BORDER)s;
        selection-background-color: %(INFO)s;
        outline: none;
    }

    /* --- Calendar popup (QDateEdit) ---------------------------------- */
    QCalendarWidget QWidget { background: %(SURFACE_HI)s; }
    QCalendarWidget QAbstractItemView {
        background: %(SURFACE_HI)s;
        selection-background-color: %(INFO)s;
        selection-color: #10212e;
        outline: none;
    }
    QCalendarWidget QToolButton {
        background: transparent; border: none; padding: 6px; margin: 2px;
    }
    QCalendarWidget QToolButton:hover { background: #3f3f3f; border-radius: 6px; }
    QCalendarWidget QMenu { background: %(SURFACE_HI)s; }
    QCalendarWidget QSpinBox { background: %(SURFACE_HI)s; }

    /* --- Tables ------------------------------------------------------ */
    QTableView {
        background: %(SURFACE)s;
        alternate-background-color: #2d2d2d;
        border: 1px solid %(BORDER)s;
        border-radius: 10px;
        gridline-color: transparent;
        selection-background-color: #37536b;
        selection-color: %(TEXT)s;
        outline: none;
    }
    QTableView::item { padding: 7px 10px; border: none; }
    QHeaderView::section {
        background: %(SURFACE_HI)s;
        color: %(MUTED)s;
        border: none;
        border-bottom: 1px solid %(BORDER)s;
        padding: 9px 10px;
        font-weight: bold;
    }
    QHeaderView::section:hover { color: %(TEXT)s; }
    QTableCornerButton::section { background: %(SURFACE_HI)s; border: none; }

    /* --- Misc -------------------------------------------------------- */
    QProgressBar {
        background: #3a3a3a; border: none; border-radius: 5px;
        height: 10px; text-align: center; color: transparent;
    }
    QProgressBar::chunk { background: %(INFO)s; border-radius: 5px; }
    QProgressBar[tone="success"]::chunk { background: %(ACCENT)s; }

    QScrollBar:vertical   { background: transparent; width: 10px; margin: 2px; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
    QScrollBar::handle {
        background: #4a4a4a; border-radius: 5px; min-height: 30px; min-width: 30px;
    }
    QScrollBar::handle:hover { background: #5a5a5a; }
    QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
    QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
    """ % {
        "BG": BG, "SURFACE": SURFACE, "SURFACE_HI": SURFACE_HI, "BORDER": BORDER,
        "TEXT": TEXT, "MUTED": MUTED, "ACCENT": ACCENT, "INFO": INFO,
        "WARNING": WARNING, "DANGER": DANGER, "FAMILY": FAMILY,
        "BIG": SIZES["big"], "TITLE": SIZES["title"], "HEAD": SIZES["head"],
        "BODY": SIZES["body"], "SMALL": SIZES["small"],
    }
