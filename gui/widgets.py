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


def cols(headers):
    """Build Tableview column specs: first column left-anchored (label),
    remaining columns right-anchored (numeric), matching how Google Sheets
    aligns this data.
    """
    return [
        {"text": h, "anchor": (W if i == 0 else E), "stretch": True}
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
