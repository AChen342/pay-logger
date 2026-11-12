"""Add Shift: form to log a shift's tips, hours, tip-out and details, plus
a table of the most recent entries."""
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import formatting, pages, widgets


class NewLog(ttk.Frame):
    """"Add Shift" screen."""

    HEADERS = formatting.TIP_HEADERS

    def __init__(self, master):
        super().__init__(master)
        widgets.makeHeader(self, "Add Shift", master, backTo=pages.HOME)

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(0, 30))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(3, weight=1)

        formBox = ttk.Labelframe(body, text="Shift Details", padding=24)
        formBox.grid(row=0, column=0, sticky="ew")
        self.form = widgets.ShiftForm(formBox, master,
                                      widgets.sectionsUsed(master.logger.df))
        self.form.pack(anchor="w")

        btnRow = ttk.Frame(formBox)
        btnRow.pack(anchor="w", pady=(18, 0))
        ttk.Button(btnRow, text="Save Shift", bootstyle="primary", width=14,
                   command=self.submitLog).pack(side=LEFT, padx=(0, 10), ipady=6)
        ttk.Button(btnRow, text="Back", bootstyle="secondary-outline", width=12,
                   command=lambda: master.showFrame(pages.HOME)).pack(side=LEFT, ipady=6)
        self.errMessage = ttk.Label(btnRow, text="", bootstyle="danger", font=master.FONT)
        self.errMessage.pack(side=LEFT, padx=(18, 0))

        ttk.Label(body, text="Recent Entries", font=master.FONT_HEAD).grid(
            row=2, column=0, sticky="w", pady=(28, 12))
        self.table = widgets.makeTable(body, self.HEADERS, height=8)
        self.table.grid(row=3, column=0, sticky="nsew")

        self._drawn = None
        self.refreshDisplay()
        self._autoDate = None
        self.form.date.bind("<<DateEntrySelected>>", lambda e: self._guessType(), add="+")
        self.setToday()

    def onShow(self):
        """Called by App.showFrame each time this screen is shown. The app
        stays open across days (and logs can be deleted elsewhere), so move
        an untouched default date forward to the current next-unlogged
        shift / today."""
        self.setToday(onlyIfUntouched=True)
        if self._drawn != self.master.stamp():
            self.refreshDisplay()

    def setToday(self, onlyIfUntouched=False):
        """Default the date to the oldest shift that still needs logging
        (see App.unloggedDates), or today if there isn't one. With
        `onlyIfUntouched`, leave it alone if the user has typed or picked a
        different date."""
        entry = self.form.date.entry
        if onlyIfUntouched and self._autoDate is not None and entry.get() != self._autoDate:
            return
        pending = self.master.unloggedDates()
        d = pending[0] if pending else self.master.today()
        self.form.date.set_date(_asDatetime(d), notify=False)
        self._autoDate = entry.get()
        self._guessType()

    def _guessType(self):
        """Pre-pick Lunch/Dinner from the calendar shift's start time for
        the chosen date; otherwise keep whatever was last picked."""
        d = self.form.date.get_date()
        start = self.master.shiftStarts.get(d.date()) if d else None
        if start is not None and start.hour + start.minute / 60 > 0:
            self.form.shiftType.set("Lunch" if start.hour < 15 else "Dinner")
        elif not self.form.shiftType.get():
            self.form.shiftType.set(_lastUsedType(self.master.logger.df) or "Dinner")

    def submitLog(self):
        """Validate the form and, if it's complete, save the shift and
        refresh the table."""
        entry, err = self.form.get()
        if err:
            self.errMessage.config(text=err)
            return
        # Saving rewrites the Google Sheet, which takes a moment -- say so
        # instead of looking frozen.
        self.errMessage.config(text="Saving…", bootstyle="secondary")
        self.update_idletasks()
        try:
            self.master.logger.addTip(entry)
        except Exception as e:
            self.errMessage.config(text=f"*Couldn't save ({type(e).__name__}) — check your connection",
                                   bootstyle="danger")
            raise
        self.errMessage.config(text="", bootstyle="danger")
        self.form.clearAmounts()
        self.form.section.configure(values=widgets.sectionsUsed(self.master.logger.df))
        self.refreshDisplay()
        self.setToday()  # next unlogged shift (or today), ready for the next log

    def refreshDisplay(self):
        """Reload the "Recent Entries" table (the 10 most recent logs,
        newest first)."""
        self._drawn = self.master.stamp()
        logs = self.master.logger.df.tail(10)[::-1]
        widgets.loadTable(self.table, self.HEADERS, formatting.tip_rows(logs))


def _asDatetime(d):
    from datetime import datetime
    return d if isinstance(d, datetime) else datetime(d.year, d.month, d.day)


def _lastUsedType(df):
    if df is None or df.empty or "Shift Type" not in df.columns:
        return None
    s = df["Shift Type"].map(formatting.text)
    s = s[s != ""]
    return s.iloc[-1] if len(s) else None
