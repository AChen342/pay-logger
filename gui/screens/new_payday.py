"""Add Payday: form to submit a paycheck's totals, plus a table of the
most recent paydays."""
import tkinter as tk

import pandas as pd
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import formatting, pages, widgets


class NewPayDay(ttk.Frame):
    """"Add Payday" screen."""

    HEADERS = ["Start", "End", "Hours", "Gross", "Tax", "Work Pay",
               "Card", "Cash", "Tips", "Before Tax", "After Tax", "Hourly"]

    def __init__(self, master):
        super().__init__(master)
        widgets.makeHeader(self, "Add Payday", master, backTo=pages.HOME)

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(0, 30))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ttk.Label(body, text="Recent Paydays", font=master.FONT_HEAD).grid(
            row=0, column=0, sticky="w", pady=(0, 12))
        self.table = widgets.makeTable(body, self.HEADERS, height=7, bootstyle="success")
        self.table.grid(row=1, column=0, sticky="nsew", pady=(0, 28))

        form = ttk.Labelframe(body, text="Payday Details", padding=24)
        form.grid(row=2, column=0, sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        ttk.Label(form, text="Start / End Dates", font=master.FONT_BOLD).grid(
            row=0, column=0, sticky="w", pady=10, padx=(0, 18))
        dateFrame = ttk.Frame(form)
        dateFrame.grid(row=0, column=1, sticky="w", pady=10)

        self.startMonth = ttk.Entry(dateFrame, width=4, validate="key", validatecommand=master.monthCmd)
        self.startMonth.pack(side=LEFT)
        ttk.Label(dateFrame, text="/", font=master.FONT_BOLD).pack(side=LEFT, padx=4)
        self.startDay = ttk.Entry(dateFrame, width=4, validate="key", validatecommand=master.dayCmd)
        self.startDay.pack(side=LEFT)
        ttk.Label(dateFrame, text="/", font=master.FONT_BOLD).pack(side=LEFT, padx=4)
        self.startYear = ttk.Entry(dateFrame, width=6, validate="key", validatecommand=master.yearCmd)
        self.startYear.pack(side=LEFT)
        widgets.CalendarButton(
            dateFrame,
            lambda: self._readDate(self.startMonth, self.startDay, self.startYear),
            lambda d: widgets.fillDateBoxes(d, self.startMonth, self.startDay, self.startYear),
        ).pack(side=LEFT, padx=(8, 0))

        ttk.Label(dateFrame, text="   to   ", font=master.FONT_BOLD).pack(side=LEFT)

        self.endMonth = ttk.Entry(dateFrame, width=4, validate="key", validatecommand=master.monthCmd)
        self.endMonth.pack(side=LEFT)
        ttk.Label(dateFrame, text="/", font=master.FONT_BOLD).pack(side=LEFT, padx=4)
        self.endDay = ttk.Entry(dateFrame, width=4, validate="key", validatecommand=master.dayCmd)
        self.endDay.pack(side=LEFT)
        ttk.Label(dateFrame, text="/", font=master.FONT_BOLD).pack(side=LEFT, padx=4)
        self.endYear = ttk.Entry(dateFrame, width=6, validate="key", validatecommand=master.yearCmd)
        self.endYear.pack(side=LEFT)
        widgets.CalendarButton(
            dateFrame,
            lambda: self._readDate(self.endMonth, self.endDay, self.endYear),
            lambda d: widgets.fillDateBoxes(d, self.endMonth, self.endDay, self.endYear),
        ).pack(side=LEFT, padx=(8, 0))

        ttk.Label(form, text="Gross Pay", font=master.FONT_BOLD).grid(
            row=1, column=0, sticky="w", pady=10, padx=(0, 18))
        self.grossPay = ttk.Entry(form, width=18, validate="key", validatecommand=master.moneyCmd)
        self.grossPay.grid(row=1, column=1, sticky="w", pady=10)

        ttk.Label(form, text="Tax Taken", font=master.FONT_BOLD).grid(
            row=2, column=0, sticky="w", pady=10, padx=(0, 18))
        self.taxAmount = ttk.Entry(form, width=18, validate="key", validatecommand=master.moneyCmd)
        self.taxAmount.grid(row=2, column=1, sticky="w", pady=10)

        btnRow = ttk.Frame(form)
        btnRow.grid(row=3, column=0, columnspan=2, sticky="w", pady=(18, 0))
        ttk.Button(btnRow, text="Submit", bootstyle="primary", width=12,
                   command=self.submitLog).pack(side=LEFT, padx=(0, 10), ipady=6)
        ttk.Button(btnRow, text="Back", bootstyle="secondary-outline", width=12,
                   command=lambda: master.showFrame(pages.HOME)).pack(side=LEFT, ipady=6)

        self.errMessage = ttk.Label(form, text="", bootstyle="danger", font=master.FONT)
        self.errMessage.grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        self.refreshDisplay()
        self.setDefaultStart()

    def setDefaultStart(self):
        """Default the start date to the day after the most recent payday's
        end date (the next pay period begins right where the last ended).
        Leaves it blank if there are no paydays yet."""
        ends = pd.to_datetime(self.master.logger.dfPayDay["End Date"], errors="coerce").dropna()
        if ends.empty:
            return
        widgets.fillDateBoxes(ends.max() + pd.Timedelta(days=1),
                              self.startMonth, self.startDay, self.startYear)

    def _readDate(self, month, day, year):
        """Month/day/year boxes -> datetime, or None if not a real date
        (used to open the calendar on / highlight the typed date)."""
        return self.master.validateFullDate(month.get(), day.get(), year.get())

    def checkFormFilled(self):
        """Return True iff every field has something in it, otherwise show
        the specific field that's missing and return False."""
        if not (self.startMonth.get() and self.startDay.get() and self.startYear.get()):
            self.errMessage.config(text="*Please fill in start date!")
            return False
        if not (self.endMonth.get() and self.endDay.get() and self.endYear.get()):
            self.errMessage.config(text="*Please fill in end date!")
            return False
        if not self.grossPay.get():
            self.errMessage.config(text="*Please enter gross pay amount!")
            return False
        if not self.taxAmount.get():
            self.errMessage.config(text="*Please enter tax amount!")
            return False
        return True

    def clearEntries(self):
        """Empty every form field after a successful submit."""
        for w in (self.startMonth, self.startDay, self.startYear,
                  self.endMonth, self.endDay, self.endYear,
                  self.grossPay, self.taxAmount):
            w.delete(0, tk.END)

    def refreshDisplay(self):
        """Reload the "Recent Paydays" table from the logger's current
        data (the 20 most recent paydays)."""
        df = self.master.logger.dfPayDay[::-1].head(20)
        widgets.loadTable(self.table, self.HEADERS, formatting.payday_rows(df))

    def submitLog(self):
        """Validate the form and, if it's complete and both dates are
        real, append a new payday and refresh the table."""
        if not self.checkFormFilled():
            return

        startDate = self.master.validateFullDate(self.startMonth.get(), self.startDay.get(), self.startYear.get())
        if startDate is None:
            self.errMessage.config(text="*Invalid Start Date!")
            return

        endDate = self.master.validateFullDate(self.endMonth.get(), self.endDay.get(), self.endYear.get())
        if endDate is None:
            self.errMessage.config(text="*Invalid End Date!")
            return

        self.errMessage.config(text="")
        self.master.logger.addPayDay((startDate, endDate, float(self.grossPay.get()), float(self.taxAmount.get())))
        self.clearEntries()
        self.refreshDisplay()
        self.setDefaultStart()  # next period starts after the one just added
