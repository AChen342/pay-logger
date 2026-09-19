"""Add New Log: form to submit a shift's tips/hours, plus a table of the
most recent entries."""
import tkinter as tk
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import formatting, pages, widgets


class NewLog(ttk.Frame):
    """"Add New Log" screen."""

    HEADERS = ["Date", "Hours", "Card", "Cash", "Total"]

    def __init__(self, master):
        super().__init__(master)
        widgets.makeHeader(self, "Add New Log", master, backTo=pages.HOME)

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(0, 30))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ttk.Label(body, text="Recent Entries", font=master.FONT_HEAD).grid(
            row=0, column=0, sticky="w", pady=(0, 12))
        self.table = widgets.makeTable(body, self.HEADERS, height=8)
        self.table.grid(row=1, column=0, sticky="nsew", pady=(0, 28))

        form = ttk.Labelframe(body, text="Log Details", padding=24)
        form.grid(row=2, column=0, sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        ttk.Label(form, text="Date", font=master.FONT_BOLD).grid(
            row=0, column=0, sticky="w", pady=10, padx=(0, 18))
        dateFrame = ttk.Frame(form)
        dateFrame.grid(row=0, column=1, sticky="w", pady=10)
        self.month = ttk.Entry(dateFrame, width=4, validate="key", validatecommand=master.monthCmd)
        self.month.pack(side=LEFT)
        ttk.Label(dateFrame, text="/", font=master.FONT_BOLD).pack(side=LEFT, padx=4)
        self.day = ttk.Entry(dateFrame, width=4, validate="key", validatecommand=master.dayCmd)
        self.day.pack(side=LEFT)
        ttk.Label(dateFrame, text="/", font=master.FONT_BOLD).pack(side=LEFT, padx=4)
        self.year = ttk.Entry(dateFrame, width=6, validate="key", validatecommand=master.yearCmd)
        self.year.pack(side=LEFT)
        widgets.CalendarButton(
            dateFrame,
            lambda: self.master.validateFullDate(self.month.get(), self.day.get(), self.year.get()),
            lambda d: widgets.fillDateBoxes(d, self.month, self.day, self.year),
        ).pack(side=LEFT, padx=(8, 0))

        fields = [
            ("Card Tip", "cardTip"),
            ("Cash Tip", "cashTip"),
            ("Hours Worked", "hours"),
        ]
        for i, (label, attr) in enumerate(fields, start=1):
            ttk.Label(form, text=label, font=master.FONT_BOLD).grid(
                row=i, column=0, sticky="w", pady=10, padx=(0, 18))
            entry = ttk.Entry(form, width=22, validate="key", validatecommand=master.moneyCmd)
            entry.grid(row=i, column=1, sticky="w", pady=10)
            setattr(self, attr, entry)

        btnRow = ttk.Frame(form)
        btnRow.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", pady=(18, 0))
        ttk.Button(btnRow, text="Submit", bootstyle="primary", width=12,
                   command=self.submitLog).pack(side=LEFT, padx=(0, 10), ipady=6)
        ttk.Button(btnRow, text="Back", bootstyle="secondary-outline", width=12,
                   command=lambda: master.showFrame(pages.HOME)).pack(side=LEFT, ipady=6)

        self.errMessage = ttk.Label(form, text="", bootstyle="danger", font=master.FONT)
        self.errMessage.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="w", pady=(12, 0))

        self.refreshDisplay()
        self._autoDate = None
        self.setToday()
        # The app stays open across days, so whenever this screen is shown
        # again, move an untouched default date forward to the new today.
        self.bind("<Map>", lambda e: self.setToday(onlyIfUntouched=True))

    def _dateBoxes(self):
        return (self.month.get(), self.day.get(), self.year.get())

    def setToday(self, onlyIfUntouched=False):
        """Default the date to today. With `onlyIfUntouched`, leave it alone
        if the user has typed or picked a different date."""
        if onlyIfUntouched and self._autoDate is not None and self._dateBoxes() != self._autoDate:
            return
        widgets.fillDateBoxes(datetime.now(), self.month, self.day, self.year)
        self._autoDate = self._dateBoxes()

    def submitLog(self):
        """Validate the form and, if it's complete and the date is real,
        append a new tip entry and refresh the table."""
        month, day, year = self.month.get(), self.day.get(), self.year.get()
        card, cash, hours = self.cardTip.get(), self.cashTip.get(), self.hours.get()

        if not (month and day and year and card and cash and hours):
            self.errMessage.config(text="*Please fill in all fields!")
            return

        date = self.master.validateFullDate(month, day, year)
        if date is None:
            self.errMessage.config(text="*Invalid date!")
            return

        self.errMessage.config(text="")
        self.master.logger.addTip((date.strftime("%m/%d/%Y"), float(card), float(cash), float(hours)))
        self.clearEntries()
        self.refreshDisplay()

    def clearEntries(self):
        """Clear the amounts and reset the date to today after a successful submit."""
        for w in (self.cardTip, self.cashTip, self.hours):
            w.delete(0, tk.END)
        self.setToday()  # date goes back to today, ready for the next log

    def refreshDisplay(self):
        """Reload the "Recent Entries" table from the logger's current
        data (the 10 most recent tip logs)."""
        logs = self.master.logger.df.tail(10)
        widgets.loadTable(self.table, self.HEADERS, formatting.tip_rows(logs))
