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
    ("＋  Add Shift", pages.ADD_SHIFT, "success"),
    ("Logs", pages.VIEW_LOGS, None),
    ("Insights", pages.INSIGHTS, None),
    ("Payday", pages.ADD_PAYDAY, None),
    ("Edit / Delete", pages.EDIT_LOGS, None),
)


RECENT_ROWS = 10  # how many shifts the "Recent shifts" card lists


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
        nav.append(widgets.button("Goals", None, self.edit_goals))
        nav.append(widgets.button("Quit", "ghost", app.close))
        self.body.addWidget(row(title_host, None, *nav, spacing=8))

        self.missed = label("", tone="warning")
        self.missed.setVisible(False)
        self.body.addWidget(self.missed)

        # --- Cards ------------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(16)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        grid.setRowStretch(1, 1)
        self.body.addLayout(grid, 1)

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
            w["pace"] = label("", tone="info")
            card.body.addWidget(w["range"])
            card.body.addWidget(w["net"])
            card.body.addWidget(w["detail"])
            card.body.addSpacing(10)
            card.body.addWidget(bar)
            card.body.addWidget(w["goal"])
            card.body.addWidget(w["pace"])
            card.body.addStretch(1)
            grid.addWidget(card, 0, col)
            self.periods[key] = w

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
        for key in ("so_far", "left", "goal"):
            self.fc[key] = label("", wrap=True)
            fcard.body.addWidget(self.fc[key])
            fcard.body.addSpacing(4)
        self.fc["upcoming"] = label("", role="muted", wrap=True)
        fcard.body.addWidget(self.fc["upcoming"])
        fcard.body.addStretch(1)
        grid.addWidget(fcard, 1, 0)

        # Recent shifts
        # The rows are built once and refilled, never rebuilt: swapping
        # widgets in and out on every refresh is both slower and a source
        # of leftovers drawn over the new rows.
        rcard = Card("Recent shifts")
        recent = QGridLayout()
        recent.setHorizontalSpacing(20)
        recent.setVerticalSpacing(9)
        recent.setColumnStretch(4, 1)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self.recent_rows = []
        for i in range(RECENT_ROWS):
            cells = {
                "when": label(),
                "type": label(role="muted"),
                "net": label(tone="accent"),
                "per": label(role="muted"),
                "note": label(role="muted"),
            }
            cells["net"].setAlignment(right)
            cells["per"].setAlignment(right)
            for col, key in enumerate(("when", "type", "net", "per", "note")):
                recent.addWidget(cells[key], i, col)
            self.recent_rows.append(cells)
        self.recent_empty = label("No shifts logged yet.", role="muted")
        recent.addWidget(self.recent_empty, RECENT_ROWS, 0, 1, 5)
        holder = QWidget()
        holder.setLayout(recent)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        rcard.body.addSpacing(6)
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
        for key in ("weekly", "monthly", "yearly"):
            start, end = stats.PERIODS[key](today)
            fcs[key] = stats.forecast(d, today, None if key == "yearly" else upcoming,
                                      start, end)

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
            w["pace"].setText(f"On pace for ~{money(fc['projected'], False)}"
                              if fc and key != "monthly" else "")

        self._fill_forecast(fcs["monthly"], app.goals.get("monthly"))
        self._fill_recent(d)

    def _fill_goal(self, w, goal, net, fc):
        gp = stats.goal_progress(goal, net, fc["projected"] if fc else None,
                                 fc["per_shift"] if fc else None)
        bar, lb = w["bar"], w["goal"]
        if gp is None:
            bar.setValue(0)
            bar.setProperty("tone", "")
            lb.setText("No goal set — click Goals")
            widgets.tone(lb, None)
        else:
            bar.setValue(int(gp["pct"] * 100))
            bar.setProperty("tone", "success" if gp["pct"] >= 1 else "")
            if gp["left"] <= 0:
                lb.setText(f"✓  {money(goal, False)} goal reached")
                widgets.tone(lb, "accent")
            else:
                lb.setText(f"{gp['pct']:.0%} of {money(goal, False)}"
                           f"  ·  {money(gp['left'], False)} to go")
                widgets.tone(lb, None)
        widgets.restyle(bar)

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
        f["so_far"].setText(f"{money(fc['so_far'])} earned so far this month")
        n = len(fc["remaining"])
        where = ("on your schedule" if fc["source"] == "calendar"
                 else "expected at your usual pace")
        f["left"].setText(f"{n} shift{'s' if n != 1 else ''} left {where}"
                          f"  ·  ~{money(fc['per_shift'], False)} per shift")

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

        if fc["source"] == "calendar" and fc["remaining"]:
            days = ", ".join(f"{u:%a} {u.month}/{u.day}" for u in fc["remaining"][:10])
            more = len(fc["remaining"]) - 10
            f["upcoming"].setText("Upcoming: " + days + (f" +{more} more" if more > 0 else ""))
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
            cells["per"].setText(f"{money(r['Net'] / r['Hours'])}/hr" if r["Hours"] > 0 else "")
            cells["note"].setText(note if len(note) <= 70 else note[:67] + "…")
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
