"""Small reusable pieces shared by the screens: the page header bar, the
data-table widget (with this app's shared styling baked in), and the
calendar date pickers.
"""
import calendar
import time
import tkinter as tk
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import Tableview

from . import formatting


def makeHeader(parent, title, master, backTo=None):
    """Top app-bar: page title on the left, a "← Home" button on the right
    (if `backTo` is given -- one of the gui.pages constants), followed by a
    hairline separator.
    """
    bar = ttk.Frame(parent)
    bar.pack(fill=X, padx=32, pady=(26, 10))
    ttk.Label(bar, text=title, font=master.FONT_TITLE).pack(side=LEFT)
    if backTo is not None:
        ttk.Button(
            bar, text="← Home", bootstyle="secondary-outline",
            command=lambda: master.showFrame(backTo)
        ).pack(side=RIGHT, ipady=4)
    ttk.Separator(parent, orient=HORIZONTAL).pack(fill=X, padx=32, pady=(0, 20))
    return bar


# Text columns are left-aligned wherever they appear; everything else is a
# number and right-aligned.
TEXT_COLUMNS = {"Type", "Section", "Notes", "Shift Type", "Day", "Group"}


def cols(headers):
    """Build Tableview column specs: first column and text columns left-
    anchored, numeric columns right-anchored, matching how Google Sheets
    aligns this data.
    """
    return [
        {"text": h, "anchor": (W if i == 0 or h in TEXT_COLUMNS else E),
         "stretch": True}
        for i, h in enumerate(headers)
    ]


def makeTable(parent, headers, height=10, searchable=False,
              paginated=False, pagesize=12, bootstyle=PRIMARY):
    """Create a Tableview with this app's comfortable row density and the
    right-aligned numeric columns Google Sheets uses.
    """
    table = Tableview(
        master=parent,
        coldata=cols(headers),
        rowdata=[],
        paginated=paginated,
        pagesize=pagesize,
        searchable=searchable,
        yscrollbar=True,
        autofit=True,
        # autoalign is intentionally off: ttkbootstrap's own numeric check
        # (str.isnumeric()) returns False for formatted amounts like
        # "42.10" and would silently re-left-align them. We already set the
        # correct per-column anchor in cols() above.
        autoalign=False,
        height=height,
        bootstyle=bootstyle,
    )
    # "Comfortable" row density (like Gmail's comfortable view) instead of
    # the theme's default compact rows, plus a bit more breathing room
    # around the column headers.
    style_name = table.view.cget("style") or "Treeview"
    s = ttk.Style()
    try:
        s.configure(style_name, rowheight=34)
        s.configure(f"{style_name}.Heading", padding=(12, 10))
    except Exception:
        pass
    return table


def loadTable(table, headers, rows):
    """Replace a Tableview's contents. `rows` must already be tuples of
    display strings -- see gui.formatting for building those from a raw
    DataFrame.
    """
    table.build_table_data(cols(headers), rows)


def fillDateBoxes(d, month, day, year):
    """Write date `d` into separate month/day/year Entry boxes (the layout
    the Add Log / Add Payday forms use)."""
    for box, value in ((month, d.month), (day, d.day), (year, d.year)):
        box.delete(0, tk.END)
        box.insert(0, str(value))


class CalendarButton(ttk.Button):
    """A calendar icon button that opens a month/year-navigable popup.

    ttkbootstrap's own DateEntry rebuilds its popup on every click (slow).
    Here the popup is built once, a moment after startup, and afterwards
    only shown/hidden and refreshed, so it opens instantly.

    Callbacks: `getDate()` -> datetime or None (what to highlight / open on),
    `onPick(datetime)` (called when a day is chosen).
    """

    def __init__(self, master, getDate, onPick):
        super().__init__(master, text="\U0001F4C5", width=3,
                         bootstyle="info-outline", command=self._toggle)
        self._getDate = getDate
        self._onPick = onPick
        self._popup = None
        self._closedAt = 0.0
        self._view = (datetime.now().year, datetime.now().month)
        self.after(300, self._build)  # warm up off the click path

    # --- Building (once) ----------------------------------------------
    def _build(self):
        if self._popup is not None:
            return
        top = tk.Toplevel(self)
        top.withdraw()
        top.overrideredirect(True)
        box = ttk.Frame(top, padding=8, bootstyle="secondary")
        box.pack()
        inner = ttk.Frame(box, padding=6)
        inner.pack()

        head = ttk.Frame(inner)
        head.grid(row=0, column=0, columnspan=7, pady=(0, 6), sticky="ew")
        # « / » jump a year, ‹ / › a month.
        for text, delta, side in (("«", -12, LEFT), ("‹", -1, LEFT)):
            ttk.Button(head, text=text, width=2, bootstyle="secondary-outline",
                       command=lambda d=delta: self._shift(d)).pack(side=side, padx=(0, 2))
        for text, delta in (("»", 12), ("›", 1)):
            ttk.Button(head, text=text, width=2, bootstyle="secondary-outline",
                       command=lambda d=delta: self._shift(d)).pack(side=RIGHT, padx=(2, 0))
        self._title = ttk.Label(head, anchor=CENTER, width=14)
        self._title.pack(side=LEFT, expand=YES, fill=X)

        for c, name in enumerate(("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")):
            ttk.Label(inner, text=name, anchor=CENTER, width=4,
                      bootstyle="secondary").grid(row=1, column=c)
        self._cells = []
        for r in range(6):
            for c in range(7):
                b = ttk.Button(inner, text="", width=4, bootstyle="secondary-link")
                b.grid(row=2 + r, column=c, padx=1, pady=1)
                self._cells.append(b)

        top.bind("<Escape>", lambda e: self._close())
        top.bind("<FocusOut>", lambda e: self.after(60, self._checkFocus))
        self._popup = top

    # --- Behavior -------------------------------------------------------
    def _toggle(self):
        if self._popup is None:
            self._build()
        if self._popup.winfo_viewable():
            return self._close()
        if time.time() - self._closedAt < 0.25:
            return  # this click just dismissed it via focus-out
        cur = self._getDate() or datetime.now()
        self._view = (cur.year, cur.month)
        self._refresh()
        self._popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 4}")
        self._popup.deiconify()
        self._popup.lift()
        self._popup.focus_force()

    def _close(self):
        self._closedAt = time.time()
        self._popup.withdraw()

    def _checkFocus(self):
        if self._popup.winfo_viewable():
            f = self.focus_get()
            if f is None or not str(f).startswith(str(self._popup)):
                self._close()

    def _shift(self, months):
        """Move the shown month by `months` (±1 month, ±12 a year)."""
        y, m = self._view
        y, m = divmod(y * 12 + (m - 1) + months, 12)
        self._view = (y, m + 1)
        self._refresh()

    def _refresh(self):
        y, m = self._view
        self._title.configure(text=datetime(y, m, 1).strftime("%B %Y"))
        sel = self._getDate()
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(y, m)
        weeks += [[0] * 7] * (6 - len(weeks))
        for i, day in enumerate(d for w in weeks for d in w):
            b = self._cells[i]
            if day == 0:
                b.configure(text="", state=DISABLED, bootstyle="secondary-link")
                continue
            picked = sel is not None and (sel.year, sel.month, sel.day) == (y, m, day)
            b.configure(text=str(day), state=NORMAL,
                        bootstyle="info" if picked else "secondary-link",
                        command=lambda d=day: self._pick(d))

    def _pick(self, day):
        y, m = self._view
        self._close()
        self._onPick(datetime(y, m, day))


class DatePicker(ttk.Frame):
    """Date field (MM/DD/YYYY) with a calendar button.

    `.entry` is the text Entry; picking a day fires <<DateEntrySelected>>
    on the picker itself.
    """
    FMT = "%m/%d/%Y"

    def __init__(self, master, width=11):
        super().__init__(master)
        self.entry = ttk.Entry(self, width=width, justify=CENTER)
        self.entry.pack(side=LEFT)
        CalendarButton(self, self.get_date, self.set_date).pack(side=LEFT, padx=(4, 0))

    def get_date(self, mark_invalid=False):
        """The typed/picked date, or None if the box is blank or not a real
        date. With `mark_invalid`, a non-blank bad value is also outlined
        red (and the outline cleared otherwise)."""
        text = self.entry.get().strip()
        try:
            d = datetime.strptime(text, self.FMT)
        except ValueError:
            d = None
        if mark_invalid:
            self.entry.state(["invalid" if (text and d is None) else "!invalid"])
        return d

    def set_date(self, d, notify=True):
        """Show date `d` (or clear the box if None). Fires
        <<DateEntrySelected>> unless `notify` is False."""
        self.entry.delete(0, tk.END)
        if d is not None:
            self.entry.insert(0, d.strftime(self.FMT))
        if notify:
            self.event_generate("<<DateEntrySelected>>")


# --- Dashboard building blocks --------------------------------------------

def card(parent, title, app, padding=18):
    """A bordered panel with a small caption on top (the look of the Tips
    graph's summary tiles, bigger). Returns (outer, body): grid/pack
    `outer`, put content in `body`."""
    outer = ttk.Frame(parent, padding=1, bootstyle="secondary")
    body = ttk.Frame(outer, padding=padding)
    body.pack(fill=BOTH, expand=YES)
    if title:
        ttk.Label(body, text=title.upper(), font=app.FONT_SMALL,
                  bootstyle="secondary").pack(anchor="w")
    return outer, body


def statTile(parent, caption, app):
    """Small caption + big value tile. Returns (tile, value_label)."""
    outer, body = card(parent, None, app, padding=(16, 10))
    ttk.Label(body, text=caption, font=app.FONT_SMALL,
              bootstyle="secondary").pack(anchor="w")
    value = ttk.Label(body, text="—", font=app.FONT_HEAD)
    value.pack(anchor="w")
    return outer, value


class ShiftForm(ttk.Frame):
    """Every field of a shift, laid out in two columns, with a live
    take-home / per-hour readout. Used by Add Shift and the Edit dialog.

    `get()` -> (entry dict for Logger.addTip/editLog, None) or
    (None, error message). `set(row)` fills it from a Daily-sheet row.
    """

    def __init__(self, master, app, sections=()):
        super().__init__(master)
        self.app = app
        lbl = lambda text, r, c: ttk.Label(self, text=text, font=app.FONT_BOLD).grid(
            row=r, column=c, sticky="w", pady=8, padx=(0 if c == 0 else 36, 14))

        # Left column: when / what.
        lbl("Date", 0, 0)
        self.date = DatePicker(self)
        self.date.grid(row=0, column=1, sticky="w")
        lbl("Shift Type", 1, 0)
        self.shiftType = ttk.Combobox(self, values=_shiftTypes(), width=12,
                                      state="readonly")
        self.shiftType.grid(row=1, column=1, sticky="w")
        lbl("Section", 2, 0)
        self.section = ttk.Combobox(self, values=list(sections), width=12)
        self.section.grid(row=2, column=1, sticky="w")
        lbl("Hours Worked", 3, 0)
        self.hours = self._money(3, 1)

        # Right column: money.
        lbl("Card Tips", 0, 2)
        self.card = self._money(0, 3)
        lbl("Cash Tips", 1, 2)
        self.cash = self._money(1, 3)
        lbl("Tip Out", 2, 2)
        self.tipOut = self._money(2, 3)
        lbl("Notes", 3, 2)
        self.notes = ttk.Entry(self, width=34)
        self.notes.grid(row=3, column=3, sticky="w")

        self.preview = ttk.Label(self, text="", font=app.FONT_BOLD, bootstyle="success")
        self.preview.grid(row=4, column=0, columnspan=4, sticky="w", pady=(14, 0))
        for e in (self.hours, self.card, self.cash, self.tipOut):
            e.bind("<KeyRelease>", lambda ev: self.updatePreview(), add="+")
        self.updatePreview()

    def _money(self, r, c):
        e = ttk.Entry(self, width=14, validate="key", validatecommand=self.app.moneyCmd)
        e.grid(row=r, column=c, sticky="w")
        return e

    @staticmethod
    def _f(entry):
        try:
            return float(entry.get())
        except ValueError:
            return None

    def updatePreview(self):
        card, cash = self._f(self.card) or 0, self._f(self.cash) or 0
        out, hours = self._f(self.tipOut) or 0, self._f(self.hours) or 0
        net = card + cash - out
        if not (card or cash or out):
            self.preview.config(text="")
            return
        per = f"   ·   {formatting.money(net / hours)}/hr" if hours > 0 else ""
        self.preview.config(text=f"Take-home  {formatting.money(net)}{per}")

    def clearAmounts(self):
        for e in (self.hours, self.card, self.cash, self.tipOut, self.notes):
            e.delete(0, tk.END)
        self.updatePreview()

    def set(self, row):
        """Fill every field from a Daily-sheet row (a pandas Series)."""
        self.date.set_date(datetime.strptime(formatting.fmtDate(row["Date"]), "%m/%d/%Y"),
                           notify=False)
        self.shiftType.set(formatting.text(row.get("Shift Type")))
        self.section.set(formatting.text(row.get("Section")))
        for e, col in ((self.hours, "Hours"), (self.card, "Card"),
                       (self.cash, "Cash"), (self.tipOut, "Tip Out")):
            e.delete(0, tk.END)
            v = formatting.num(row.get(col))
            if v or col != "Tip Out":
                e.insert(0, formatting.fmt(v))
        self.notes.delete(0, tk.END)
        self.notes.insert(0, formatting.text(row.get("Notes")))
        self.updatePreview()

    def get(self):
        date = self.date.get_date(mark_invalid=True)
        if date is None:
            return None, "*Invalid date!"
        if not (self.card.get() and self.cash.get() and self.hours.get()):
            return None, "*Please fill in card tips, cash tips and hours!"
        if not self.shiftType.get():
            return None, "*Please pick a shift type!"
        return {
            "date": date.strftime("%m/%d/%Y"),
            "card": float(self.card.get()),
            "cash": float(self.cash.get()),
            "hours": float(self.hours.get()),
            "tipOut": self._f(self.tipOut) or 0.0,
            "shiftType": self.shiftType.get(),
            "section": self.section.get().strip(),
            "notes": self.notes.get().strip(),
        }, None


def _shiftTypes():
    import logger  # top-level module; imported lazily to keep widgets light
    return list(logger.SHIFT_TYPES)


def sectionsUsed(df):
    """Sections already used in the Daily sheet, most-used first (for the
    Section dropdown)."""
    if df is None or df.empty or "Section" not in df.columns:
        return []
    s = df["Section"].map(formatting.text)
    return list(s[s != ""].value_counts().index)
