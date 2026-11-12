"""Add Payday: record a paycheck. Hours and tip totals for the pay period
are summed from the logged shifts by the logger."""
from datetime import timedelta

import pandas as pd

import formatting
from .. import pages, widgets
from ..widgets import Card, DataTable, DateEdit, MoneyEdit, label, row
from .base import Screen
from .view_logs import PAYDAY_HEADERS


class AddPayday(Screen):
    """"Add Payday" screen."""

    title = "Add Payday"

    def __init__(self, app):
        super().__init__(app)

        card = Card("Payday details", padding=22, spacing=14)
        self.start = DateEdit()
        self.end = DateEdit()
        self.gross = MoneyEdit(placeholder="0.00")
        self.tax = MoneyEdit(placeholder="0.00")

        def field(caption, *rest):
            lb = label(caption, role="caption")
            lb.setFixedWidth(120)
            card.body.addWidget(row(lb, *rest, None, spacing=12))

        field("PAY PERIOD", self.start, label("to", role="muted"), self.end)
        field("GROSS PAY", self.gross)
        field("TAX TAKEN", self.tax)

        self.submit_button = widgets.button("Save Payday", "primary", self.submit)
        self.status = label("")
        card.body.addWidget(row(
            self.submit_button,
            widgets.button("Back", "ghost", lambda: app.show_page(pages.HOME)),
            self.status, None))
        self.body.addWidget(card)

        self.body.addWidget(label("Recent paydays", role="head"))
        self.table = DataTable(PAYDAY_HEADERS, fit="stretch")
        self.body.addWidget(self.table, 1)

        self.refresh_now()
        self.default_start()

    def on_show(self):
        super().on_show()
        self.default_start()

    def default_start(self):
        """Start the next period the day after the last one ended."""
        ends = pd.to_datetime(self.app.logger.dfPayDay.get("End Date"),
                              errors="coerce").dropna() \
            if "End Date" in self.app.logger.dfPayDay.columns else pd.Series(dtype="datetime64[ns]")
        if not ends.empty:
            self.start.set_date((ends.max() + pd.Timedelta(days=1)).date())
            if self.end.get_date() <= self.start.get_date():
                self.end.set_date(self.start.get_date() + timedelta(days=13))

    # --- Saving ---------------------------------------------------------
    def submit(self):
        gross, tax = self.gross.value(), self.tax.value()
        if gross is None or tax is None:
            self.status.setText("Fill in gross pay and tax.")
            widgets.tone(self.status, "danger")
            return
        start, end = self.start.get_date(), self.end.get_date()
        if end < start:
            self.status.setText("The end date is before the start date.")
            widgets.tone(self.status, "danger")
            return

        self.submit_button.setEnabled(False)
        self.status.setText("Saving…")
        widgets.tone(self.status, "muted")
        entry = (pd.Timestamp(start).to_pydatetime(),
                 pd.Timestamp(end).to_pydatetime(), gross, tax)
        self.app.run_task(lambda: self.app.logger.addPayDay(entry), self._saved)

    def _saved(self, _result, error):
        self.submit_button.setEnabled(True)
        if error is not None:
            self.status.setText(f"Couldn't save ({type(error).__name__}) — check your connection")
            widgets.tone(self.status, "danger")
            print(f"Saving a payday failed ({type(error).__name__}: {error})")
            return
        self.status.setText("Saved ✓")
        widgets.tone(self.status, "accent")
        self.gross.clear()
        self.tax.clear()
        self.refresh_now()
        self.default_start()

    # --- Drawing --------------------------------------------------------
    def refresh(self):
        df = self.app.logger.dfPayDay[::-1].head(20)
        self.table.load(PAYDAY_HEADERS, formatting.payday_rows(df))
