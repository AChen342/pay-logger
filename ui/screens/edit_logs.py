"""Edit / Delete Log: pick a logged shift and change or remove it."""
from PySide6.QtWidgets import QMessageBox

import formatting
from .. import pages, widgets
from ..widgets import DataTable, label, row
from .base import Screen
from .dialogs import EditShiftDialog


class EditLogs(Screen):
    """"Edit / Delete Log" screen."""

    title = "Edit / Delete Log"

    def __init__(self, app):
        super().__init__(app)
        # Table rows are newest-first, so this maps a table row back to its
        # index in logger.df (what editLog/deleteLog take). Rebuilt on
        # every refresh, because pandas re-indexes after a delete.
        self._index_map = []

        self.body.addWidget(label("Pick a shift, then edit or delete it "
                                  "(double-click a row to edit).", role="muted"))
        self.table = DataTable(formatting.TIP_HEADERS, searchable=True,
                               selectable=True)
        self.table.activated.connect(lambda _: self.edit_selected())
        self.body.addWidget(self.table, 1)

        self.status = label("")
        self.edit_button = widgets.button("Edit selected", "primary", self.edit_selected)
        self.delete_button = widgets.button("Delete selected", "danger", self.delete_selected)
        self.body.addWidget(row(
            self.edit_button, self.delete_button,
            widgets.button("Back", "ghost", lambda: app.show_page(pages.HOME)),
            self.status, None))

        self.refresh_now()

    # --- Selection ------------------------------------------------------
    def _selected(self):
        """(df index, row) of the selected shift, or (None, None)."""
        pos = self.table.selected_row()
        if pos is None or pos >= len(self._index_map):
            self.status.setText("Pick a shift first.")
            widgets.tone(self.status, "muted")
            return None, None
        index = self._index_map[pos]
        return index, self.app.logger.df.loc[index]

    def edit_selected(self):
        index, shift = self._selected()
        if index is None:
            return
        EditShiftDialog(self.app, shift,
                        lambda entry: self._write(
                            lambda: self.app.logger.editLog(index, entry), "Saved ✓")).exec()

    def delete_selected(self):
        index, shift = self._selected()
        if index is None:
            return
        when = formatting.fmtDate(shift["Date"])
        net = formatting.num(shift["Card"]) + formatting.num(shift["Cash"]) \
            - formatting.num(shift["Tip Out"])
        ok = QMessageBox.question(
            self, "Delete shift",
            f"Delete the shift on {when} ({formatting.money(net)} take-home)?\n"
            "This also updates your weekly, monthly and payday totals.")
        if ok == QMessageBox.StandardButton.Yes:
            self._write(lambda: self.app.logger.deleteLog(index), "Deleted ✓")

    # --- Saving ---------------------------------------------------------
    def _write(self, work, done_text):
        """Run a logger write off the UI thread (it rewrites the sheet)."""
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.status.setText("Saving…")
        widgets.tone(self.status, "muted")
        self.app.run_task(work, lambda _r, err: self._written(err, done_text))

    def _written(self, error, done_text):
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        if error is not None:
            self.status.setText(f"Couldn't save ({type(error).__name__}) — check your connection")
            widgets.tone(self.status, "danger")
            print(f"Writing a change failed ({type(error).__name__}: {error})")
            return
        self.status.setText(done_text)
        widgets.tone(self.status, "accent")
        self.refresh_now()

    # --- Drawing --------------------------------------------------------
    def refresh(self):
        logs = self.app.logger.df[::-1]
        self._index_map = list(logs.index)
        self.table.load(formatting.TIP_HEADERS, formatting.tip_rows(logs))
