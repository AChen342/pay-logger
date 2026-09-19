"""Edit / Delete Log: pick a row from the tip-log table and change or
remove it."""
import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import formatting, pages, widgets


class EditLogDialog(tk.Toplevel):
    """Modal form for changing one tip log's date, card, cash and hours.

    `values` is the row's current (date "%m/%d/%Y", card, cash, hours) as
    display strings; `onSave(date_str, card, cash, hours)` is called with
    the validated new values (floats for the amounts) when Save is clicked.
    """

    def __init__(self, app, values, onSave):
        # Plain tk.Toplevel: ttkbootstrap's own Toplevel takes `title` as its
        # first argument (and differs between versions), so it can't be
        # given the parent window positionally.
        super().__init__(app)
        self.title("Edit Log")
        self.app, self.onSave = app, onSave
        self.transient(app)
        self.resizable(False, False)

        form = ttk.Frame(self, padding=24)
        form.pack()
        date, card, cash, hours = values

        ttk.Label(form, text="Date", font=app.FONT_BOLD).grid(
            row=0, column=0, sticky="w", pady=10, padx=(0, 18))
        self.date = widgets.DatePicker(form)
        self.date.grid(row=0, column=1, sticky="w", pady=10)
        self.date.entry.insert(0, date)

        self.fields = {}
        for i, (label, key, val) in enumerate(
                (("Card Tip", "card", card), ("Cash Tip", "cash", cash),
                 ("Hours Worked", "hours", hours)), start=1):
            ttk.Label(form, text=label, font=app.FONT_BOLD).grid(
                row=i, column=0, sticky="w", pady=10, padx=(0, 18))
            e = ttk.Entry(form, width=22, validate="key", validatecommand=app.moneyCmd)
            e.grid(row=i, column=1, sticky="w", pady=10)
            e.insert(0, val)
            self.fields[key] = e

        btns = ttk.Frame(form)
        btns.grid(row=4, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(btns, text="Save", bootstyle="primary", width=12,
                   command=self._save).pack(side=LEFT, padx=(0, 10), ipady=4)
        ttk.Button(btns, text="Cancel", bootstyle="secondary-outline", width=12,
                   command=self.destroy).pack(side=LEFT, ipady=4)
        self.err = ttk.Label(form, text="", bootstyle="danger", font=app.FONT)
        self.err.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        # Centered over the app window, and modal.
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.fields["card"].focus_set()

    def _save(self):
        date = self.date.get_date()
        vals = {k: e.get().strip() for k, e in self.fields.items()}
        if date is None:
            self.err.config(text="*Invalid date!")
            return
        if not all(vals.values()):
            self.err.config(text="*Please fill in all fields!")
            return
        self.onSave(date.strftime("%m/%d/%Y"), float(vals["card"]),
                    float(vals["cash"]), float(vals["hours"]))
        self.destroy()


class DeleteLogs(ttk.Frame):
    """"Edit / Delete Log" screen."""

    HEADERS = ["Date", "Hours", "Card", "Cash", "Total"]

    def __init__(self, master):
        super().__init__(master)
        # Maps table row position -> that row's real index in
        # master.logger.df, so a selected table row can be turned back
        # into the DataFrame index deleteLog() needs. The table shows rows
        # newest-first (reversed from the DataFrame's own order), so this
        # can't be computed from position alone -- it's rebuilt every time
        # loadLogs() runs.
        self._index_map = []

        widgets.makeHeader(self, "Edit / Delete Log", master, backTo=pages.HOME)

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(0, 30))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ttk.Label(
            body, text="Select a row, then Edit Selected or Delete Selected.",
            font=master.FONT, bootstyle="secondary"
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.table = widgets.makeTable(body, self.HEADERS, height=18, searchable=True, bootstyle="danger")
        self.table.grid(row=1, column=0, sticky="nsew")
        self.table.view.configure(selectmode="browse")

        btnRow = ttk.Frame(body)
        btnRow.grid(row=2, column=0, sticky="w", pady=(20, 0))
        ttk.Button(btnRow, text="Refresh", bootstyle="secondary-outline", width=14,
                   command=self.loadLogs).pack(side=LEFT, padx=(0, 10), ipady=6)
        ttk.Button(btnRow, text="Edit Selected", bootstyle="primary", width=16,
                   command=self.editSelected).pack(side=LEFT, padx=(0, 10), ipady=6)
        ttk.Button(btnRow, text="Delete Selected", bootstyle="danger", width=16,
                   command=self.deleteSelected).pack(side=LEFT, padx=(0, 10), ipady=6)
        ttk.Button(btnRow, text="Back", bootstyle="secondary-outline", width=14,
                   command=lambda: master.showFrame(pages.HOME)).pack(side=LEFT, ipady=6)

        self.loadLogs()

    def loadLogs(self):
        """Reload the table from the logger's current data and rebuild
        `_index_map` to match."""
        logs = self.master.logger.df[::-1]
        widgets.loadTable(self.table, self.HEADERS, formatting.tip_rows(logs))
        self._index_map = list(logs.index)

    def _selectedIndex(self):
        """DataFrame index of the selected table row, or None."""
        selected = self.table.get_rows(selected=True)
        if not selected:
            return None
        return self._index_map[self.table.tablerows.index(selected[0])]

    def editSelected(self):
        """Open the edit dialog for the selected row; on Save, write the
        change through the logger and reload the table."""
        df_index = self._selectedIndex()
        if df_index is None:
            return
        row = self.master.logger.df.loc[df_index]
        values = (formatting.fmtDate(row["Date"]), formatting.fmt(row["Card"]),
                  formatting.fmt(row["Cash"]), formatting.fmt(row["Hours"]))

        def save(date, card, cash, hours):
            self.master.logger.editLog(df_index, (date, card, cash, hours))
            self.loadLogs()

        EditLogDialog(self.master, values, save)

    def deleteSelected(self):
        """Delete whichever row is selected (if any), then fully reload
        the table -- pandas re-indexes on delete, so `_index_map` can't
        just be patched in place."""
        selected = self.table.get_rows(selected=True)
        if not selected:
            return
        row = selected[0]
        pos = self.table.tablerows.index(row)
        df_index = self._index_map[pos]
        self.master.logger.deleteLog(df_index)
        self.loadLogs()
