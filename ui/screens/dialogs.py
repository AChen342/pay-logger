"""The two popups: income goals, and editing one shift."""
from PySide6.QtWidgets import QDialog, QVBoxLayout

from .. import widgets
from ..widgets import MoneyEdit, ShiftForm, label, row


class _Dialog(QDialog):
    """Shared chrome: title, padding, and the Save / Cancel strip."""

    def __init__(self, app, title, save_text="Save"):
        super().__init__(app)
        self.app = app
        self.setWindowTitle(title)
        self.setModal(True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(26, 24, 26, 22)
        self.body.setSpacing(14)

        self.error = label("", tone="danger")
        self.save_button = widgets.button(save_text, "primary", self.save)
        self._buttons = row(self.save_button,
                            widgets.button("Cancel", "ghost", self.reject),
                            self.error, None)

    def finish(self):
        """Call once the dialog's own content is in `body`."""
        self.body.addWidget(self._buttons)

    def save(self):
        """Overridden by subclasses."""


class GoalsDialog(_Dialog):
    """Take-home tip goals, and the days usually worked."""

    DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def __init__(self, app):
        super().__init__(app, "Settings")
        self.body.addWidget(label("Take-home tip goals", role="head"))
        self.body.addWidget(label("Leave a box empty for no goal.", role="muted"))
        self.boxes = {}
        for key, text in (("weekly", "Weekly"), ("monthly", "Monthly"),
                          ("yearly", "Yearly")):
            box = MoneyEdit(width=150, placeholder="0.00")
            if app.goals.get(key):
                box.setText(f"{app.goals[key]:g}")
            caption = label(text, role="caption")
            caption.setFixedWidth(80)
            self.body.addWidget(row(caption, box, None))
            self.boxes[key] = box
        self.body.addSpacing(10)
        self.body.addWidget(widgets.separator())
        self.body.addSpacing(10)
        self.body.addWidget(label("Days you usually work", role="head"))
        self.body.addWidget(label(
            "Used to project the rest of the month before your manager "
            "posts the schedule. Leave all off to count only the shifts "
            "actually on your calendar.", role="muted", wrap=True))
        self.day_buttons = []
        for index, name in enumerate(self.DAYS):
            button = widgets.button(name, "day")
            button.setCheckable(True)
            button.setChecked(index in app.workdays)
            self.day_buttons.append(button)
        self.body.addWidget(row(*self.day_buttons, None, spacing=6))

        self.finish()
        self.boxes["weekly"].setFocus()

    def save(self):
        self.app.set_goals(
            {k: (b.value() if (b.value() or 0) > 0 else None)
             for k, b in self.boxes.items()},
            workdays=[i for i, b in enumerate(self.day_buttons) if b.isChecked()])
        self.accept()


class EditShiftDialog(_Dialog):
    """Change any field of one logged shift. `on_save(entry)` does the
    actual saving (the caller owns the logger)."""

    def __init__(self, app, shift_row, on_save):
        super().__init__(app, "Edit Shift", save_text="Save changes")
        self._on_save = on_save
        self.form = ShiftForm(widgets.sections_used(app.logger.df))
        self.form.fill(shift_row)
        self.form.submitted.connect(self.save)
        self.body.addWidget(self.form)
        self.finish()
        self.form.card.setFocus()

    def save(self):
        entry, err = self.form.values()
        if err:
            self.error.setText(err)
            return
        self._on_save(entry)
        self.accept()
