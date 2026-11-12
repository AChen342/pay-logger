"""Edit / Delete Log: pick a row from the tip-log table and change or
remove it."""
import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import formatting, pages, widgets


class EditLogDialog(tk.Toplevel):
    """Modal form for changing every field of one tip log.

    `row` is the log's current Daily-sheet row (a pandas Series);
    `onSave(entry)` is called with the validated entry dict (see
    Logger.addTip) when Save is clicked.
    """

    def __init__(self, app, row, onSave):
        # Plain tk.Toplevel: ttkbootstrap's own Toplevel takes `title` as its
        # first argument (and differs between versions), so it can't be
        # given the parent window positionally.
        super().__init__(app)
        self.title("Edit Shift")
        self.app, self.onSave = app, onSave
        self.transient(app)
        self.resizable(False, False)

        box = ttk.Frame(self, padding=24)
        box.pack()
        self.form = widgets.ShiftForm(box, app, widgets.sectionsUsed(app.logger.df))
        self.form.pack(anchor="w")
        self.form.set(row)

        btns = ttk.Frame(box)
        btns.pack(anchor="w", pady=(16, 0))
        ttk.Button(btns, text="Save", bootstyle="primary", width=12,
                   command=self._save).pack(side=LEFT, padx=(0, 10), ipady=4)
        ttk.Button(btns, text="Cancel", bootstyle="secondary-outline", width=12,
                   command=self.destroy).pack(side=LEFT, ipady=4)
        self.err = ttk.Label(btns, text="", bootstyle="danger", font=app.FONT)
        self.err.pack(side=LEFT, padx=(16, 0))

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        # Centered over the app window, and modal.
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.form.card.focus_set()

    def _save(self):
        entry, err = self.form.get()
        if err:
            self.err.config(text=err)
            return
        self.onSave(entry)
        self.destroy()


class DeleteLogs(ttk.Frame):
    """"Edit / Delete Log" screen."""

    HEADERS = formatting.TIP_HEADERS

    def __init__(self, master):
        super().__init__(master)
        # Maps table row position -> that row's real index in
        # master.logger.df, so a selected table row can be turned back
        # into the DataFrame index deleteLog() needs. The table shows rows
        # newest-first (reversed from the DataFrame's own order), so this
        # can't be computed from position alone -- it's rebuilt every time
        # loadLogs() runs.
        self._index_map = []
        self._drawn = None

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

    def onShow(self):
        """Reload when the screen is shown, if logs changed since."""
        if self._drawn != self.master.stamp():
            self.loadLogs()

    def loadLogs(self):
        """Reload the table from the logger's current data and rebuild
        `_index_map` to match."""
        self._drawn = self.master.stamp()
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

        def save(entry):
            self.master.logger.editLog(df_index, entry)
            self.loadLogs()

        EditLogDialog(self.master, row, save)

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
