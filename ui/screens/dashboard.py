"""The Dashboard: this week / month / year at a glance, goal progress, the
month-end forecast, and the latest shifts -- plus the buttons to every
other screen.

All the arithmetic is in the top-level `stats` module; this file lays the
numbers out.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QProgressBar,
                               QSizePolicy, QVBoxLayout, QWidget)

import stats
from formatting import money
from .. import pages, widgets
from ..widgets import Card, label, row
from .base import Screen
from .dialogs import GoalsDialog

PERIOD_CARDS = (("weekly", "This week"), ("monthly", "This month"),
                ("yearly", "This year"))

NAV = (
    ("Add shift", pages.ADD_SHIFT, "primary"),
    ("Logs", pages.VIEW_LOGS, "ghost"),
    ("Insights", pages.INSIGHTS, "ghost"),
    ("Payday", pages.ADD_PAYDAY, "ghost"),
    ("Edit", pages.EDIT_LOGS, "ghost"),
)


RECENT_ROWS = 8  # how many shifts the "Recent shifts" card lists


class Dashboard(Screen):
    """Landing page."""

    def __init__(self, app):
        super().__init__(app)

        # --- Top bar ----------------------------------------------------
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("Pay Logger", role="title"))
        self.subtitle = label("", role="muted")
        titles.addWidget(self.subtitle)
        title_host = QWidget()
        title_host.setLayout(titles)

        nav = [widgets.button(text, variant,
                              lambda _=False, p=page: app.show_page(p))
               for text, page, variant in NAV]
        nav.append(widgets.button("Goals", "ghost", self.edit_goals))
        nav.append(widgets.button("Quit", "ghost", app.close))
        self.body.addWidget(row(title_host, None, *nav, spacing=6))
        self.body.addSpacing(8)

        self.missed = label("", tone="warning", role="figure")
        self.missed.setVisible(False)
        self.body.addWidget(self.missed)

        # --- Cards ------------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(22)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        self.body.addLayout(grid)
        self.body.addStretch(1)

        self.periods = {}
        for col, (key, caption) in enumerate(PERIOD_CARDS):
            card = Card(caption)
            w = {}
            w["range"] = label("", role="muted")
            w["net"] = label("—", role="big")
            w["detail"] = label("", role="muted")
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            w["bar"] = bar
            w["goal"] = label("", role="muted")
            card.body.addWidget(w["range"])
            card.body.addSpacing(2)
            card.body.addWidget(w["net"])
            card.body.addWidget(w["detail"])
            card.body.addSpacing(16)
            card.body.addWidget(bar)
            card.body.addSpacing(2)
            card.body.addWidget(w["goal"])
            card.body.addStretch(1)
            grid.addWidget(card, 0, col)
            self.periods[key] = w

        # Next shift -- what the upcoming scheduled shift is likely to bring
        ncard = Card("Next shift")
        self.nx = {}
        self.nx["when"] = label("", role="muted")
        self.nx["mid"] = label("—", role="big")
        self.nx["range"] = label("", role="muted")
        self.nx["basis"] = label("", role="muted", wrap=True)
        self.nx["score"] = label("", role="muted", wrap=True)
        for key in ("when", "mid", "range"):
            ncard.body.addWidget(self.nx[key])
        ncard.body.addSpacing(10)
        ncard.body.addWidget(self.nx["basis"])
        ncard.body.addWidget(self.nx["score"])
        ncard.body.addStretch(1)

        # Forecast
        fcard = Card("Month-end forecast")
        self.fc = {}
        self.fc["projected"] = label("—", role="big", tone="info")
        self.fc["range"] = label("", role="muted")
        fcard.body.addWidget(self.fc["projected"])
        fcard.body.addWidget(self.fc["range"])
        fcard.body.addSpacing(8)
        fcard.body.addWidget(widgets.separator())
        fcard.body.addSpacing(8)
        for key in ("so_far", "left", "likely", "goal"):
            self.fc[key] = label("", wrap=True)
            fcard.body.addWidget(self.fc[key])
            fcard.body.addSpacing(4)
        self.fc["upcoming"] = label("", role="muted", wrap=True)
        fcard.body.addWidget(self.fc["upcoming"])
        fcard.body.addStretch(1)
        left_column = QVBoxLayout()
        left_column.setSpacing(22)
        left_column.addWidget(ncard)
        left_column.addWidget(fcard)
        left_host = QWidget()
        left_host.setLayout(left_column)
        grid.addWidget(left_host, 1, 0)

        # Recent shifts
        # The rows are built once and refilled, never rebuilt: swapping
        # widgets in and out on every refresh is both slower and a source
        # of leftovers drawn over the new rows.
        rcard = Card("Recent shifts")
        recent = QGridLayout()
        recent.setHorizontalSpacing(26)
        recent.setVerticalSpacing(12)
        recent.setColumnStretch(3, 1)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self.recent_rows = []
        for i in range(RECENT_ROWS):
            cells = {
                "when": label(),
                "type": label(role="muted"),
                "net": label(role="figure"),
                "note": label(role="muted"),
            }
            cells["net"].setAlignment(right)
            for col, key in enumerate(("when", "type", "net", "note")):
                recent.addWidget(cells[key], i, col)
            self.recent_rows.append(cells)
        self.recent_empty = label("No shifts logged yet.", role="muted")
        recent.addWidget(self.recent_empty, RECENT_ROWS, 0, 1, 4)
        holder = QWidget()
        holder.setLayout(recent)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        rcard.body.addSpacing(8)
        rcard.body.addWidget(holder)
        rcard.body.addStretch(1)
        link = widgets.button("View all logs  →", "link",
                              lambda: app.show_page(pages.VIEW_LOGS))
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(link)
        rcard.body.addLayout(bottom)
        grid.addWidget(rcard, 1, 1, 1, 2)

        self.refresh_now()

    # --- Drawing --------------------------------------------------------
    def refresh(self):
        app = self.app
        today = app.today()
        self.subtitle.setText(f"{today:%A, %B} {today.day}")
        self._fill_missed()

        d = stats.shifts(app.logger.df)
        so_far = stats.period_totals(d, today)
        upcoming = app.upcomingShifts

        # Week and month use the calendar's remaining shifts; the year is
        # too far out for that, so it uses recent pace.
        fcs = {}
        unlogged = app.unlogged_dates()
        for key in ("weekly", "monthly", "yearly"):
            start, end = stats.PERIODS[key](today)
            fcs[key] = stats.forecast(
                d, today,
                None if key == "yearly" else upcoming, start, end,
                # The year is too far out to fill from usual days; it keeps
                # the recent-pace estimate.
                workdays=() if key == "yearly" else app.workdays,
                unlogged=unlogged)

        for key, w in self.periods.items():
            t, fc = so_far[key], fcs[key]
            start, end = stats.PERIODS[key](today)
            w["range"].setText(f"{start:%b} {start.day} – {end:%b} {end.day}")
            w["net"].setText(money(t["net"]))
            n = t["shifts"]
            w["detail"].setText(
                f"{n} shift{'s' if n != 1 else ''}  ·  {t['hours']:g} hrs  ·  "
                f"{money(t['per_hour'])}/hr" if n else "No shifts logged yet")
            self._fill_goal(w, app.goals.get(key), t["net"], fc)

        self._fill_next_shift(d)
        self._fill_forecast(fcs["monthly"], app.goals.get("monthly"))
        self._fill_recent(d)

    def _fill_goal(self, w, goal, net, fc):
        gp = stats.goal_progress(goal, net, fc["projected"] if fc else None,
                                 fc["per_shift"] if fc else None)
        bar, lb = w["bar"], w["goal"]
        bar.setVisible(gp is not None)
        lb.setVisible(gp is not None)
        if gp is None:
            pass
        else:
            bar.setValue(int(gp["pct"] * 100))
            bar.setProperty("tone", "" if gp["pct"] >= 1 else "muted")
            if gp["left"] <= 0:
                lb.setText(f"✓  {money(goal, False)} goal reached")
                widgets.tone(lb, "accent")
            else:
                lb.setText(f"{gp['pct']:.0%} of {money(goal, False)}"
                           f"  ·  {money(gp['left'], False)} to go")
                widgets.tone(lb, None)
        widgets.restyle(bar)

    def _fill_next_shift(self, d):
        """The next shift on the calendar, and what it's likely to bring.
        Deliberately shown as a range with its own track record -- a single
        number would be more confident than the data allows."""
        nx = self.nx
        upcoming = self.app.upcomingShifts
        when = upcoming[0] if upcoming else None
        guess = stats.predict_shift(d, when) if when else None

        if guess is None:
            for key in ("mid", "range", "basis", "score"):
                nx[key].setText("")
            nx["mid"].setText("—")
            if when is not None:          # scheduled, but too little history
                nx["when"].setText(f"{when:%a, %b} {when.day}")
                nx["basis"].setText("Not enough logged shifts to predict yet.")
            else:
                nx["when"].setText("Nothing scheduled" if upcoming is not None
                                   else "Opened without the calendar check")
            return

        # Built by hand rather than with strftime: "%-I" (no leading zero)
        # is a GNU extension and raises on Windows.
        start = self.app.shiftStarts.get(when)
        clock = ""
        if start and (start.hour or start.minute):
            hour = start.hour % 12 or 12
            clock = f"  ·  {hour}:{start.minute:02d} {'am' if start.hour < 12 else 'pm'}"
        nx["when"].setText(f"{when:%a, %b} {when.day}{clock}")
        nx["mid"].setText("~" + money(guess["mid"], False))
        nx["range"].setText(f"usually {money(guess['lo'], False)} – "
                            f"{money(guess['hi'], False)}")
        nx["basis"].setText(f"From {guess['basis']} ({guess['samples']} shifts).")

        score = stats.prediction_accuracy(d)
        nx["score"].setText(
            f"Past guesses were off by about {money(score['median_err'], False)}, "
            f"and {round(score['coverage'] * 10)} in 10 landed in the range."
            if score else "")

    def _fill_forecast(self, fc, goal):
        f = self.fc
        if fc is None:
            f["projected"].setText("—")
            f["range"].setText("Log a few shifts to see a forecast")
            for k in ("so_far", "left", "goal", "upcoming"):
                f[k].setText("")
            return
        f["projected"].setText(money(fc["projected"], False))
        f["range"].setText(f"Likely between {money(fc['low'], False)} and "
                           f"{money(fc['high'], False)}")
        f["so_far"].setText(f"{money(fc['so_far'], False)} earned so far")
        scheduled, pending, likely = fc["scheduled"], fc["pending"], fc["likely"]
        if fc["source"] == "pace":
            n = len(fc["remaining"])
            f["left"].setText(f"{n} shift{'s' if n != 1 else ''} expected at your "
                              f"usual pace  ·  ~{money(fc['per_shift'], False)} each")
        else:
            n = len(scheduled)
            line = (f"{n} shift{'s' if n != 1 else ''} scheduled"
                    f"  ·  ~{money(fc['scheduled_value'], False)}")
            if pending:
                line += f"  ·  {len(pending)} worked, not logged yet"
            f["left"].setText(line)

        days = stats.describe_days(self.app.workdays)
        if likely:
            f["likely"].setText(
                f"{len(likely)} more likely on {days}"
                f"  ·  ~{money(fc['likely_value'], False)}")
            widgets.tone(f["likely"], None)
        elif not self.app.workdays and fc["source"] == "calendar":
            f["likely"].setText("Your usual days aren't set, so this counts only "
                                "what's on the calendar.")
            widgets.tone(f["likely"], "muted")
        else:
            f["likely"].setText("")

        gp = stats.goal_progress(goal, fc["so_far"], fc["projected"], fc["per_shift"])
        goal_label = f["goal"]
        if gp is None:
            goal_label.setText("")
        elif gp["left"] <= 0:
            goal_label.setText(f"Monthly goal of {money(goal, False)} reached")
            widgets.tone(goal_label, "accent")
        elif gp["extra_shifts"] == 0:
            goal_label.setText(f"On track for your {money(goal, False)} goal")
            widgets.tone(goal_label, "accent")
        else:
            k = gp["extra_shifts"]
            goal_label.setText(f"Pick up ~{k} more shift{'s' if k != 1 else ''} "
                               f"to hit your {money(goal, False)} goal")
            widgets.tone(goal_label, "warning")

        if fc["source"] == "calendar" and scheduled:
            dates = "   ".join(f"{u:%a} {u.month}/{u.day}" for u in scheduled[:4])
            f["upcoming"].setText("Next up   " + dates)
        elif fc["source"] == "pace":
            f["upcoming"].setText("Opened without the calendar check, so this "
                                  "is based on how often you've worked lately.")
        else:
            f["upcoming"].setText("")

    def _fill_recent(self, d):
        rows = list(d.tail(RECENT_ROWS).iloc[::-1].iterrows())
        self.recent_empty.setVisible(not rows)
        for i, cells in enumerate(self.recent_rows):
            if i >= len(rows):
                for cell in cells.values():
                    cell.setVisible(False)
                continue
            r = rows[i][1]
            note = r["Notes"]
            if r["Section"]:
                note = f"Section {r['Section']}" + (f"  ·  {note}" if note else "")
            cells["when"].setText(f"{r['Date']:%a %m/%d}")
            cells["type"].setText(r["Type"] or "—")
            cells["net"].setText(money(r["Net"]))
            cells["note"].setText(note if len(note) <= 64 else note[:61] + "…")
            for cell in cells.values():
                cell.setVisible(True)

    def _fill_missed(self):
        pending = self.app.unlogged_dates()
        if pending:
            days = ", ".join(f"{d:%a %m/%d}" for d in pending)
            noun = "shift" if len(pending) == 1 else "shifts"
            self.missed.setText(f"⚠  Unlogged {noun}: {days}")
        self.missed.setVisible(bool(pending))

    # --- Goals ----------------------------------------------------------
    def edit_goals(self):
        GoalsDialog(self.app).exec()
