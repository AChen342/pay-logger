"""Add Shift: the form for one shift's tips, hours, tip-out and details,
plus the most recent entries.

Saving writes the whole Daily tab back to Google Sheets, which takes a few
seconds, so it runs off the UI thread (App.run_task) and the window stays
usable while the button shows "Saving…".
"""
import formatting
from .. import pages, widgets
from ..widgets import Card, DataTable, ShiftForm, label, row
from .base import Screen


class AddShift(Screen):
    """"Add Shift" screen."""

    title = "Add Shift"

    def __init__(self, app):
        super().__init__(app)
        self._auto_date = None

        card = Card("Shift details", padding=22, spacing=12)
        self.form = ShiftForm(widgets.sections_used(app.logger.df))
        self.form.submitted.connect(self.save)
        card.body.addWidget(self.form)

        self.save_button = widgets.button("Save Shift", "primary", self.save)
        self.status = label("")
        card.body.addWidget(row(
            self.save_button,
            widgets.button("Back", "ghost", lambda: app.show_page(pages.HOME)),
            self.status, None))
        self.body.addWidget(card)

        self.body.addWidget(label("Recent entries", role="head"))
        self.table = DataTable(formatting.TIP_HEADERS)
        self.body.addWidget(self.table, 1)

        self.refresh_now()
        self.reset_date()

    # --- Showing --------------------------------------------------------
    def on_show(self):
        super().on_show()
        self.reset_date(only_if_untouched=True)
        self.form.card.setFocus()

    def reset_date(self, only_if_untouched=False):
        """Default the date to the oldest shift still needing a log, or
        today. With `only_if_untouched`, leave a date the user picked."""
        if only_if_untouched and self._auto_date is not None \
                and self.form.date.get_date() != self._auto_date:
            return
        pending = self.app.unlogged_dates()
        self.form.date.set_date(pending[0] if pending else self.app.today())
        self._auto_date = self.form.date.get_date()
        self.guess_type()

    def guess_type(self):
        """Pre-pick Lunch/Dinner from the calendar shift's start time for
        the chosen date."""
        start = self.app.shiftStarts.get(self.form.date.get_date())
        if start is not None and (start.hour or start.minute):
            self.form.shift_type.setCurrentText("Lunch" if start.hour < 15 else "Dinner")

    # --- Saving ---------------------------------------------------------
    def save(self):
        entry, err = self.form.values()
        if err:
            self.status.setText(err)
            widgets.tone(self.status, "danger")
            return

        self.save_button.setEnabled(False)
        self.status.setText("Saving…")
        widgets.tone(self.status, "muted")
        # The logger writes to Google Sheets here; everything that touches
        # Qt happens in done(), back on the UI thread.
        self.app.run_task(lambda: self.app.logger.addTip(entry), self._saved)

    def _saved(self, _result, error):
        self.save_button.setEnabled(True)
        if error is not None:
            self.status.setText(f"Couldn't save ({type(error).__name__}) — check your connection")
            widgets.tone(self.status, "danger")
            print(f"Saving a shift failed ({type(error).__name__}: {error})")
            return
        self.status.setText("Saved ✓")
        widgets.tone(self.status, "accent")
        self.form.clear_amounts()
        self.form.set_sections(widgets.sections_used(self.app.logger.df))
        self.refresh_now()
        self.reset_date()

    # --- Drawing --------------------------------------------------------
    def refresh(self):
        logs = self.app.logger.df.tail(12)[::-1]
        self.table.load(formatting.TIP_HEADERS, formatting.tip_rows(logs))
