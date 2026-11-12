"""Reusable pieces the screens are built from: cards, stat tiles, the data
table, the money/date inputs, the shift form, and the chart canvas.

Nothing here knows about the app's data -- screens hand these widgets
display strings and get values back -- so each one can be read on its own.
"""
from datetime import date, datetime

from PySide6.QtCore import QDate, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QDoubleValidator, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QTableView,
                               QVBoxLayout, QWidget)

import logger
from . import theme

DATE_FMT = "MM/dd/yyyy"

# Columns holding text rather than numbers: left-aligned wherever they turn up.
TEXT_COLUMNS = {"Type", "Section", "Notes", "Shift Type", "Day", "Date",
                "Start", "End", "Week Ending", "Month", "Year"}


# --- Small helpers --------------------------------------------------------

def restyle(w):
    """Re-apply the stylesheet to `w` after one of its dynamic properties
    changed (Qt doesn't notice on its own)."""
    w.style().unpolish(w)
    w.style().polish(w)


def label(text="", role=None, tone=None, wrap=False):
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    if tone:
        lb.setProperty("tone", tone)
    if wrap:
        lb.setWordWrap(True)
    return lb


def tone(widget, value):
    """Recolor a label (None clears it)."""
    widget.setProperty("tone", value or "")
    restyle(widget)


def button(text, variant=None, on_click=None):
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click is not None:
        b.clicked.connect(on_click)
    return b


def separator():
    line = QFrame()
    line.setObjectName("sep")
    line.setFixedHeight(1)
    return line


def row(*widgets, spacing=10, stretch_at=None):
    """A horizontal strip of widgets (ints become fixed-width spacers)."""
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for w in widgets:
        if isinstance(w, int):
            lay.addSpacing(w)
        elif w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w)
    if stretch_at is not None:
        lay.insertStretch(stretch_at, 1)
    host.layout = lay
    return host


class Card(QFrame):
    """A white panel with a hairline border and an optional small caption
    at the top. Add content to `.body` (a QVBoxLayout)."""

    def __init__(self, caption=None, padding=22, spacing=5):
        super().__init__()
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        if caption:
            self.body.addWidget(label(caption.upper(), role="caption"))


class StatTile(QWidget):
    """Caption above a value, with no box around it -- the spacing does the
    separating. `.set(text)`."""

    def __init__(self, caption, tone_=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.addWidget(label(caption.upper(), role="caption"))
        self.value = label("—", role="head", tone=tone_)
        lay.addWidget(self.value)

    def set(self, text):
        self.value.setText(text)


# --- Inputs ---------------------------------------------------------------

class MoneyEdit(QLineEdit):
    """A number box: digits and up to 2 decimals only."""

    def __init__(self, width=130, placeholder=""):
        super().__init__()
        v = QDoubleValidator(0.0, 1_000_000.0, 2)
        v.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(v)
        self.setFixedWidth(width)
        self.setPlaceholderText(placeholder)

    def value(self):
        """The number typed, or None if the box is empty/unparseable."""
        try:
            return float(self.text())
        except ValueError:
            return None

    def set_value(self, v):
        self.setText("" if v is None else f"{float(v):.2f}")


class DateEdit(QDateEdit):
    """MM/DD/YYYY with a calendar popup (Qt's own, styled in theme.py)."""

    def __init__(self, when=None):
        super().__init__()
        self.setDisplayFormat(DATE_FMT)
        self.setCalendarPopup(True)
        self.setFixedWidth(140)
        self.set_date(when or date.today())

    def set_date(self, d):
        if isinstance(d, datetime):
            d = d.date()
        self.setDate(QDate(d.year, d.month, d.day))

    def get_date(self):
        q = self.date()
        return date(q.year(), q.month(), q.day())


# --- Table ----------------------------------------------------------------

def _sort_key(text):
    """What a cell should sort by: a date, a number, or its text."""
    s = str(text).strip()
    if not s:
        return (0, 0.0)
    for fmt in ("%m/%d/%Y", "%a %m/%d", "%m/%d/%y", "%m/%Y"):
        try:
            return (1, datetime.strptime(s, fmt).timestamp())
        except ValueError:
            pass
    try:
        return (1, float(s.replace("$", "").replace(",", "").replace("/hr", "")))
    except ValueError:
        return (2, s.lower())


class _Cell(QStandardItem):
    """A table cell that sorts by value (so $1,000 beats $9) rather than
    by the characters shown."""

    def __init__(self, text, right):
        super().__init__(str(text))
        self.setEditable(False)
        self._key = _sort_key(text)
        self.setTextAlignment(
            (Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft)
            | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        a, b = self._key, getattr(other, "_key", None)
        return a < b if b is not None else True


class DataTable(QWidget):
    """A sortable (and optionally searchable) table of display strings.

    `load(headers, rows)` replaces the contents; `selected_row()` gives the
    position in `rows` of the selected line, or None.
    """

    activated = Signal(int)

    def __init__(self, headers=(), searchable=False, rows_visible=None,
                 selectable=False, fit="contents"):
        super().__init__()
        self._fit = fit
        self._user_sorted = False  # until a header is clicked, keep the
                                   # order the rows were handed to us in
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.search = None
        if searchable:
            self.search = QLineEdit()
            self.search.setPlaceholderText("Search…")
            self.search.setClearButtonEnabled(True)
            lay.addWidget(self.search)

        self.model = QStandardItemModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)  # search every column
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        if self.search is not None:
            self.search.textChanged.connect(self.proxy.setFilterFixedString)

        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(False)
        self.view.setShowGrid(False)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(40)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection if selectable
            else QAbstractItemView.SelectionMode.NoSelection)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus if selectable
                                 else Qt.FocusPolicy.NoFocus)
        self.view.doubleClicked.connect(
            lambda _: self.activated.emit(self.selected_row() or 0))
        head = self.view.horizontalHeader()
        head.setHighlightSections(False)
        head.setSortIndicatorShown(False)
        head.sectionClicked.connect(self._clicked_header)
        self.set_fit(fit)
        lay.addWidget(self.view, 1)

        if rows_visible:
            # Header + N rows (plus the frame), so a short table sits where
            # the layout expects it without growing a scrollbar.
            self.view.setMinimumHeight(54 + 40 * rows_visible)
        if headers:
            self.load(headers, [])

    def fit_to_rows(self, n, cap=None):
        """Size the table to exactly `n` rows (no empty space, no scrollbar).
        For short breakdowns whose length varies."""
        n = max(1, min(n, cap or n))
        height = 54 + 40 * n
        self.view.setMinimumHeight(height)
        self.view.setMaximumHeight(height)

    def set_fit(self, fit):
        """How columns share the width: "stretch" (even, nothing cut off --
        for narrow tables) or "contents" (as wide as needed, last column
        takes the slack -- for tables with a long Notes column)."""
        self._fit = fit
        head = self.view.horizontalHeader()
        if fit == "stretch":
            head.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            head.setStretchLastSection(False)
        else:
            head.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            head.setStretchLastSection(True)

    def _clicked_header(self, _column):
        self._user_sorted = True
        self.view.horizontalHeader().setSortIndicatorShown(True)

    def load(self, headers, rows):
        """Replace the contents. `rows` are tuples of display strings."""
        head = self.view.horizontalHeader()
        keep, order = head.sortIndicatorSection(), head.sortIndicatorOrder()
        self.view.setSortingEnabled(False)
        self.model.clear()
        self.model.setHorizontalHeaderLabels(list(headers))
        rights = [h not in TEXT_COLUMNS and i != 0 for i, h in enumerate(headers)]
        for r in rows:
            self.model.appendRow([_Cell(v, rights[i] if i < len(rights) else True)
                                  for i, v in enumerate(r)])
        self.view.setSortingEnabled(True)
        if self._user_sorted and 0 <= keep < len(headers):
            self.view.sortByColumn(keep, order)
        else:  # keep the order the caller gave (usually newest first)
            self.proxy.sort(-1)
            head.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            head.setSortIndicatorShown(False)
        self.set_fit(self._fit)

    def selected_row(self):
        """Position in the last-loaded `rows` of the selected line (the
        table may be sorted or filtered), or None."""
        idx = self.view.selectionModel().selectedRows()
        if not idx:
            return None
        return self.proxy.mapToSource(idx[0]).row()


# --- Charts ---------------------------------------------------------------

class ChartView(QWidget):
    """Hosts one matplotlib figure. `figure` is built lazily on the first
    `draw(fn)` so a screen that is never opened never pays for it.

    While the window is minimized (the app starts that way when nothing
    needs logging) this widget has no size, and rendering a 0x0 figure
    fails -- on Windows with "OSError: [Errno 22] Invalid argument". So a
    draw that arrives too early is held and done on the first resize that
    gives the widget room.
    """

    MIN_SIZE = 40  # px: below this, matplotlib has nothing to render into

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self.figure = None
        self.canvas = None
        self._pending = None   # a build held until the widget has a size

    def draw(self, build):
        """`build(fig)` draws into (and returns) the figure."""
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        if self.width() < self.MIN_SIZE or self.height() < self.MIN_SIZE:
            self._pending = build
            return None
        self._pending = None
        self.figure = build(self.figure)
        if self.canvas is None:
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.canvas.setStyleSheet(f"background: {theme.CHART.bg};")
            self._lay.addWidget(self.canvas)
        self.canvas.draw_idle()
        return self.canvas

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pending is not None:
            self.draw(self._pending)


# --- Shift form -----------------------------------------------------------

class ShiftForm(QWidget):
    """Every field of a shift in two columns, with a live take-home and
    per-hour readout underneath.

    `values()` -> (entry dict for Logger.addTip/editLog, None) or
    (None, error message). `fill(row)` loads a Daily-sheet row into it.
    """

    submitted = Signal()

    def __init__(self, sections=()):
        super().__init__()
        from formatting import money

        self._money = money
        grid = QHBoxLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(56)

        left = QVBoxLayout()
        left.setSpacing(16)
        right = QVBoxLayout()
        right.setSpacing(16)
        for col in (left, right):
            holder = QWidget()
            holder.setLayout(col)
            grid.addWidget(holder)
        grid.addStretch(1)

        def field(column, text, widget):
            lb = label(text, role="caption")
            lb.setFixedWidth(108)
            column.addWidget(row(lb, widget, None, spacing=14))
            return widget

        self.date = field(left, "DATE", DateEdit())
        self.shift_type = field(left, "SHIFT TYPE", QComboBox())
        self.shift_type.addItems(list(logger.SHIFT_TYPES))
        self.shift_type.setFixedWidth(140)
        self.section = field(left, "SECTION", QComboBox())
        self.section.setEditable(True)
        self.section.setFixedWidth(140)
        self.set_sections(sections)
        self.hours = field(left, "HOURS", MoneyEdit(width=140, placeholder="0.00"))

        self.card = field(right, "CARD TIPS", MoneyEdit(placeholder="0.00"))
        self.cash = field(right, "CASH TIPS", MoneyEdit(placeholder="0.00"))
        self.tip_out = field(right, "TIP OUT", MoneyEdit(placeholder="0.00"))
        self.notes = field(right, "NOTES", QLineEdit())
        self.notes.setMinimumWidth(280)
        self.notes.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Fixed)

        self.preview = label("", role="head", tone="accent")
        left.addSpacing(8)
        left.addWidget(self.preview)

        for box in (self.card, self.cash, self.tip_out, self.hours):
            box.textChanged.connect(self._update_preview)
            box.returnPressed.connect(self.submitted.emit)
        self.notes.returnPressed.connect(self.submitted.emit)
        self._update_preview()

    # --- contents -----------------------------------------------------
    def set_sections(self, sections):
        """Refresh the Section dropdown's suggestions, keeping what's typed."""
        current = self.section.currentText()
        self.section.clear()
        self.section.addItems([""] + [s for s in sections])
        self.section.setCurrentText(current)

    def clear_amounts(self):
        for box in (self.hours, self.card, self.cash, self.tip_out):
            box.clear()
        self.notes.clear()
        self._update_preview()

    def fill(self, row):
        """Load a Daily-sheet row (a pandas Series) into the form."""
        import formatting as fmt

        when = fmt.parse_date(row.get("Date"))
        if when:
            self.date.set_date(when)
        self.shift_type.setCurrentText(fmt.text(row.get("Shift Type")) or "Dinner")
        self.section.setCurrentText(fmt.text(row.get("Section")))
        for box, col in ((self.hours, "Hours"), (self.card, "Card"),
                         (self.cash, "Cash"), (self.tip_out, "Tip Out")):
            v = fmt.num(row.get(col))
            box.set_value(v if (v or col != "Tip Out") else None)
        self.notes.setText(fmt.text(row.get("Notes")))
        self._update_preview()

    def values(self):
        card, cash = self.card.value(), self.cash.value()
        hours = self.hours.value()
        if card is None or cash is None or hours is None:
            return None, "Fill in card tips, cash tips and hours."
        return {
            "date": self.date.get_date().strftime("%m/%d/%Y"),
            "card": card,
            "cash": cash,
            "hours": hours,
            "tipOut": self.tip_out.value() or 0.0,
            "shiftType": self.shift_type.currentText(),
            "section": self.section.currentText().strip(),
            "notes": self.notes.text().strip(),
        }, None

    def _update_preview(self):
        card = self.card.value() or 0
        cash = self.cash.value() or 0
        out = self.tip_out.value() or 0
        hours = self.hours.value() or 0
        if not (card or cash or out):
            self.preview.setText("")
            return
        net = card + cash - out
        per = f"   ·   {self._money(net / hours)}/hr" if hours > 0 else ""
        self.preview.setText(f"Take-home  {self._money(net)}{per}")


def sections_used(df):
    """Sections already used in the Daily sheet, most-used first."""
    import formatting as fmt

    if df is None or df.empty or "Section" not in df.columns:
        return []
    s = df["Section"].map(fmt.text)
    return list(s[s != ""].value_counts().index)


