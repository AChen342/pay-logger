"""View Logs' Graph View: the controls, the summary tiles, and the
interactive tip chart.

The figure itself is built by the top-level `charts` module (no Qt in it);
this file is the Qt side -- widgets, and the hover highlight/tooltip,
which is blitted over a cached render so moving the mouse stays cheap.
"""

from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget

import charts
from .. import theme, widgets
from ..widgets import ChartView, DateEdit, StatTile, label, row

STAT_TILES = (("total", "Take-home"), ("avg_shift", "Avg per shift"),
              ("avg_hour", "Avg per hour"), ("hours", "Hours worked"),
              ("best", "Best day"))


class TipsGraph(QWidget):
    """Stacked card/cash bars (tip-outs hang below zero) per day, week,
    month or year, over a date range."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._drawn = None   # (controls, App.stamp()) of the last draw
        self._hover = None   # index of the highlighted bar
        self._bg = None      # cached render the hover artists blit over

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.view_by = QComboBox()
        self.view_by.addItems(list(charts.GRANULARITIES))
        self.view_by.setFixedWidth(120)
        self.metric = QComboBox()
        self.metric.addItems(list(charts.METRICS))
        self.metric.setFixedWidth(150)
        today = app.today()
        self.start = DateEdit(today.replace(month=1, day=1))
        self.end = DateEdit(today)
        lay.addWidget(row(
            label("VIEW BY", role="caption"), self.view_by, 18,
            label("SHOW", role="caption"), self.metric, 18,
            label("FROM", role="caption"), self.start,
            label("TO", role="caption"), self.end, 8,
            widgets.button("Reset range", "ghost", self.reset_range), None,
            spacing=10))

        tiles = []
        self.tiles = {}
        for key, caption in STAT_TILES:
            self.tiles[key] = StatTile(caption)
            tiles.append(self.tiles[key])
        lay.addSpacing(4)
        lay.addWidget(row(*tiles, None, spacing=40))

        self.chart = ChartView()
        lay.addWidget(self.chart, 1)

        for box in (self.view_by, self.metric):
            box.currentIndexChanged.connect(self.draw)
        for box in (self.start, self.end):
            box.dateChanged.connect(self.draw)

    # --- Drawing --------------------------------------------------------
    def stamp(self):
        return (self.view_by.currentText(), self.metric.currentText(),
                self.start.get_date(), self.end.get_date(), self.app.stamp())

    def refresh(self):
        """Redraw if anything changed since the last draw (keeping the
        range the user picked)."""
        if self._drawn != self.stamp():
            self.draw()

    def reset_range(self):
        today = self.app.today()
        self.start.set_date(today.replace(month=1, day=1))
        self.end.set_date(today)
        self.draw()

    def draw(self):
        self._drawn = self.stamp()
        df = self.app.logger.df
        start, end = self.start.get_date(), self.end.get_date()
        self._fill_tiles(charts.summary(df, start, end))

        first = self.chart.canvas is None
        self.chart.draw(lambda fig: charts.tips_figure(
            df, self.view_by.currentText(), start, end, fig=fig,
            metric=self.metric.currentText(), palette=theme.CHART))
        if first:
            canvas = self.chart.canvas
            canvas.mpl_connect("draw_event", self._cache_background)
            canvas.mpl_connect("motion_notify_event", self._on_hover)
            canvas.mpl_connect("axes_leave_event", lambda e: self._hide_tip())
        self._hover = None

    def _fill_tiles(self, st):
        if st is None:
            text = dict.fromkeys(self.tiles, "—")
        else:
            text = {
                "total": f"${st['total']:,.2f}",
                "avg_shift": f"${st['avg_shift']:,.2f}",
                "avg_hour": f"${st['avg_hour']:,.2f}",
                "hours": f"{st['hours']:,.1f}",
                "best": f"${st['best_amount']:,.0f}  ({st['best_date']:%m/%d/%y})",
            }
        for key, value in text.items():
            self.tiles[key].set(value)

    # --- Hover: highlight + tooltip --------------------------------------
    # Only the two "animated" artists are redrawn over a cached copy of the
    # last full render, so moving the mouse never re-renders the figure.
    def _cache_background(self, _event):
        canvas = self.chart.canvas
        self._bg = canvas.copy_from_bbox(self.chart.figure.bbox)

    def _blit(self, data, show):
        canvas = self.chart.canvas
        if self._bg is None:
            return
        canvas.restore_region(self._bg)
        if show:
            data["ax"].draw_artist(data["hl"])
            data["ax"].draw_artist(data["ann"])
        canvas.blit(self.chart.figure.bbox)

    def _hide_tip(self):
        data = getattr(self.chart.figure, "tip_data", None)
        if data and self._hover is not None:
            data["ann"].set_visible(False)
            data["hl"].set_visible(False)
            self._blit(data, False)
        self._hover = None

    def _on_hover(self, event):
        data = getattr(self.chart.figure, "tip_data", None)
        if not data or event.inaxes is not data["ax"] or event.xdata is None:
            return self._hide_tip()
        i = int(round(event.xdata))
        heights = data["heights"]
        over = (0 <= i < len(heights)
                and abs(event.xdata - i) <= data["width"] / 2
                and 0 <= event.ydata <= heights[i])
        if not over:
            return self._hide_tip()

        ann, hl = data["ann"], data["hl"]
        if i != self._hover:
            self._hover = i
            hl.set_bounds(i - data["width"] / 2, 0, data["width"], heights[i])
            hl.set_visible(True)
            ann.set_text(data["tooltips"][i])
        # Flip the tooltip toward the free side so it never runs off.
        w, h = self.chart.canvas.get_width_height()
        left, below = event.x > w * 0.7, event.y > h * 0.65
        ann.xy = (event.xdata, event.ydata)
        ann.set_ha("right" if left else "left")
        ann.set_va("top" if below else "bottom")
        ann.xyann = (-14 if left else 14, -14 if below else 14)
        ann.set_visible(True)
        self._blit(data, True)
