"""Insights: where the shifts pay off. For a chosen range -- headline
numbers, average take-home by weekday (chart), tables by shift type and
section, and the best and slowest shifts."""
from datetime import timedelta

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

import charts
import stats
from formatting import money

from .. import theme
from ..widgets import Card, ChartView, DataTable, StatTile, label, row
from .base import Screen

RANGES = ("Last 30 days", "Last 90 days", "This year", "All time")

TILES = (("net", "Take-home"), ("shifts", "Shifts"),
         ("per_shift", "Avg per shift"), ("per_hour", "Avg per hour"))

GROUP_HEADERS = ["Shifts", "Avg shift", "Per hour"]
# Narrow tables, so: the weekday is folded into the date and the headers
# are kept short.
SHIFT_HEADERS = ["Date", "Type", "Take-home", "$/hr"]
GROUPS = (("Type", "Shift Type", "By shift type", 3),
          ("Section", "Section", "By section", 3))


class Insights(Screen):
    """"Insights" screen."""

    title = "Insights"

    def __init__(self, app):
        super().__init__(app)

        self.range = QComboBox()
        self.range.addItems(list(RANGES))
        self.range.setCurrentText(RANGES[1])
        self.range.setFixedWidth(160)
        self.range.currentIndexChanged.connect(self.refresh_now)

        self.tiles = {}
        tiles = []
        for key, caption in TILES:
            self.tiles[key] = StatTile(caption)
            tiles.append(self.tiles[key])
        self.body.addWidget(row(self.range, 44, *tiles, None, spacing=40))
        self.body.addSpacing(6)

        columns = QHBoxLayout()
        columns.setSpacing(32)
        self.body.addLayout(columns, 1)

        # Left: weekday chart, then best / slowest shifts side by side.
        left = QVBoxLayout()
        left.setSpacing(16)
        chart_card = Card("Average take-home per shift")
        self.chart = ChartView()
        chart_card.body.addWidget(self.chart, 1)
        left.addWidget(chart_card, 1)
        self.best = DataTable(SHIFT_HEADERS, rows_visible=5)
        self.worst = DataTable(SHIFT_HEADERS, rows_visible=5)
        best_col = QVBoxLayout()
        best_col.setSpacing(6)
        best_col.addWidget(label("Best shifts", role="head"))
        best_col.addWidget(self.best)
        worst_col = QVBoxLayout()
        worst_col.setSpacing(6)
        worst_col.addWidget(label("Slowest shifts", role="head"))
        worst_col.addWidget(self.worst)
        pair = QHBoxLayout()
        pair.setSpacing(28)
        for col in (best_col, worst_col):
            host = QWidget()
            host.setLayout(col)
            pair.addWidget(host)
        left.addLayout(pair)
        left_host = QWidget()
        left_host.setLayout(left)
        columns.addWidget(left_host, 3)

        # Right: breakdown tables.
        right = QVBoxLayout()
        right.setSpacing(10)
        self.groups = {}
        for key, first_col, caption, rows_visible in GROUPS:
            if key != GROUPS[0][0]:
                right.addSpacing(18)
            right.addWidget(label(caption, role="head"))
            table = DataTable([first_col] + GROUP_HEADERS, fit="stretch")
            table.fit_to_rows(rows_visible)
            right.addWidget(table)
            self.groups[key] = (first_col, table)
        right.addSpacing(18)
        self.note = label("", role="muted", wrap=True)
        right.addWidget(self.note)
        right.addStretch(1)
        right_host = QWidget()
        right_host.setLayout(right)
        columns.addWidget(right_host, 2)

    # --- Drawing --------------------------------------------------------
    def stamp(self):
        return (self.range.currentText(), self.app.stamp())

    def _bounds(self):
        today = self.app.today()
        choice = self.range.currentText()
        if choice == "Last 30 days":
            return today - timedelta(days=29), today
        if choice == "Last 90 days":
            return today - timedelta(days=89), today
        if choice == "This year":
            return today.replace(month=1, day=1), today
        return None, None

    def refresh(self):
        d = stats.between(stats.shifts(self.app.logger.df), *self._bounds())
        totals = stats.totals(d)
        for key, tile in self.tiles.items():
            v = totals[key]
            tile.set(str(v) if key == "shifts"
                     else f"{v:,.1f}" if key == "hours" else money(v))

        for key, (first_col, table) in self.groups.items():
            g = stats.breakdown(d, key)
            table.fit_to_rows(max(len(g), 1), cap=8)
            table.load([first_col] + GROUP_HEADERS, [
                (r["Group"], str(int(r["Shifts"])), money(r["Avg shift"]),
                 money(r["Per hour"]) if r["Per hour"] == r["Per hour"] else "—")
                for _, r in g.iterrows()])

        for table, best in ((self.best, True), (self.worst, False)):
            table.load(SHIFT_HEADERS, [
                (f"{r['Date']:%a %m/%d}", r["Type"] or "—", money(r["Net"]),
                 money(r["Net"] / r["Hours"]) if r["Hours"] > 0 else "")
                for _, r in stats.ranked(d, 5, best).iterrows()])

        weekday = stats.breakdown(d, "Weekday")
        self.chart.draw(lambda fig: charts.weekday_figure(
            weekday, fig=fig, palette=theme.CHART))

        untagged = int(((d["Type"] == "") & (d["Hours"] > 0)).sum())
        self.note.setText(
            f"{untagged} shift{'s' if untagged != 1 else ''} in this range have no "
            "shift type or section (logged before those existed) — they count "
            "everywhere except these two tables." if untagged else "")
