"""The Tips graph panel shown by View Logs' "Graph View": controls (view by /
metric / date range), summary tiles, and the interactive chart.

Chart drawing and the numbers live in gui.charts; this module is the Tk
side -- the widgets, and the hover highlight/tooltip. Like the screens it
only depends on other gui modules, never on App.
"""
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from . import charts, widgets

# (key, caption) for the summary tiles, in display order.
STAT_TILES = (("total", "Total tips"), ("avg_shift", "Avg per shift"),
              ("avg_hour", "Avg per hour"), ("hours", "Hours worked"),
              ("best", "Best day"))


class TipsGraph(ttk.Frame):
    """Stacked card/cash tip bars per day/week/month/year over a date range.

    Call `refresh()` whenever the panel is shown: it resets the range to
    "start of this year -> today" and redraws from the logger's current data.
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._gran = ttk.StringVar(value="Day")
        self._metric = ttk.StringVar(value=charts.METRICS[0])
        self._canvas = None     # built once, on first draw, then reused
        self._fig = None
        self._bg = None         # cached render the hover artists blit over
        self._hoverIdx = None   # bar currently highlighted
        self._lastKey = None    # (view, metric, from, to) of the last draw

        self._buildControls()
        self._buildStats()
        self.chartHost = ttk.Frame(self)
        self.chartHost.pack(fill=BOTH, expand=YES)

    # --- Layout ----------------------------------------------------------
    def _buildControls(self):
        bar = ttk.Frame(self)
        bar.pack(fill=X, pady=(0, 8))

        def label(text):
            ttk.Label(bar, text=text, font=self.app.FONT_SMALL,
                      bootstyle="secondary").pack(side=LEFT, padx=(0, 6))

        def dropdown(var, values, width, gap):
            box = ttk.Combobox(bar, textvariable=var, state="readonly",
                               values=list(values), width=width, bootstyle="info")
            box.pack(side=LEFT, padx=(0, gap))
            box.bind("<<ComboboxSelected>>", lambda e: self._draw())

        label("View by")
        dropdown(self._gran, charts.GRANULARITIES, 8, 20)
        label("Show")
        dropdown(self._metric, charts.METRICS, 13, 24)

        # Click the calendar button to pick a date; typing MM/DD/YYYY works too.
        pickers = []
        for name in ("From", "To"):
            label(name)
            picker = widgets.DatePicker(bar)
            picker.pack(side=LEFT, padx=(0, 16))
            picker.bind("<<DateEntrySelected>>", lambda e: self._draw())
            picker.entry.bind("<Return>", lambda e: self._draw())
            picker.entry.bind("<FocusOut>", lambda e: self._draw(), add="+")
            pickers.append(picker)
        self._from, self._to = pickers
        ttk.Button(bar, text="Reset range", bootstyle="secondary-outline",
                   command=self._resetRange).pack(side=LEFT)

    def _buildStats(self):
        row = ttk.Frame(self)
        row.pack(fill=X, pady=(0, 10))
        self._stat = {}
        for key, caption in STAT_TILES:
            tile = ttk.Frame(row, padding=(14, 8), bootstyle="secondary")
            tile.pack(side=LEFT, padx=(0, 10))
            inner = ttk.Frame(tile, padding=(12, 6))
            inner.pack()
            ttk.Label(inner, text=caption, font=self.app.FONT_SMALL,
                      bootstyle="secondary").pack(anchor="w")
            self._stat[key] = ttk.Label(inner, text="—", font=self.app.FONT_HEAD)
            self._stat[key].pack(anchor="w")

    # --- Range + drawing -------------------------------------------------
    def refresh(self):
        """Reset to the default range and redraw from current data."""
        self._lastKey = None
        self._resetRange()

    def _resetRange(self):
        """From = January 1st of this year, To = today."""
        today = datetime.now()
        self._from.set_date(today.replace(month=1, day=1), notify=False)
        self._to.set_date(today, notify=False)
        self._draw()

    def _draw(self):
        start = self._from.get_date(mark_invalid=True)
        end = self._to.get_date(mark_invalid=True)
        # Skip the (comparatively expensive) redraw when nothing changed --
        # e.g. a date box losing focus without being edited.
        key = (self._gran.get(), self._metric.get(), start, end)
        if key == self._lastKey and self._canvas is not None:
            return
        self._lastKey = key

        df = self.app.logger.df
        self._updateStats(charts.summary(df, start, end))
        fig = charts.tips_figure(df, self._gran.get(), start, end,
                                 fig=self._fig, metric=self._metric.get())
        if self._canvas is None:
            self._fig = fig
            self._buildCanvas()
        self._hoverIdx = None
        self._canvas.draw()

    def _buildCanvas(self):
        """Built once and reused: recreating the canvas widget on every
        change is what made the chart area flash white."""
        self._canvas = FigureCanvasTkAgg(self._fig, master=self.chartHost)
        widget = self._canvas.get_tk_widget()
        widget.configure(bg=charts.BG, highlightthickness=0)
        widget.pack(fill=BOTH, expand=YES)
        self._canvas.mpl_connect("draw_event", self._cacheBackground)
        self._canvas.mpl_connect("motion_notify_event", self._onHover)
        self._canvas.mpl_connect("axes_leave_event", lambda e: self._hideTip())

    def _updateStats(self, st):
        """Fill the summary tiles from charts.summary() output (None =
        no shifts in range)."""
        if st is None:
            text = dict.fromkeys(self._stat, "—")
        else:
            text = {
                "total": f"${st['total']:,.2f}",
                "avg_shift": f"${st['avg_shift']:,.2f}",
                "avg_hour": f"${st['avg_hour']:,.2f}",
                "hours": f"{st['hours']:,.1f}",
                "best": f"${st['best_amount']:,.2f}  ({st['best_date']:%m/%d/%y})",
            }
        for key, value in text.items():
            self._stat[key].configure(text=value)

    # --- Hover: highlight + tooltip ---------------------------------------
    # Moving the mouse must stay cheap, so instead of re-rendering the whole
    # figure only the two "animated" hover artists (highlight box, tooltip)
    # are drawn over a cached copy of the last full render (blitting).
    def _cacheBackground(self, event):
        self._bg = self._canvas.copy_from_bbox(self._fig.bbox)

    def _blitHover(self, data, show):
        if self._bg is None:
            return
        self._canvas.restore_region(self._bg)
        if show:
            data["ax"].draw_artist(data["hl"])
            data["ax"].draw_artist(data["ann"])
        self._canvas.blit(self._fig.bbox)

    def _hideTip(self):
        data = getattr(self._fig, "tip_data", None)
        if data and self._hoverIdx is not None:
            data["ann"].set_visible(False)
            data["hl"].set_visible(False)
            self._blitHover(data, False)
        self._hoverIdx = None

    def _onHover(self, event):
        """Highlight the hovered bar and show its tooltip next to the cursor."""
        data = getattr(self._fig, "tip_data", None)
        if not data or event.inaxes is not data["ax"] or event.xdata is None:
            return self._hideTip()
        i = int(round(event.xdata))
        heights = data["heights"]
        over = (0 <= i < len(heights)
                and abs(event.xdata - i) <= data["width"] / 2
                and 0 <= event.ydata <= heights[i])
        if not over:
            return self._hideTip()

        ann, hl = data["ann"], data["hl"]
        if i != self._hoverIdx:
            self._hoverIdx = i
            hl.set_bounds(i - data["width"] / 2, 0, data["width"], heights[i])
            hl.set_visible(True)
            ann.set_text(data["tooltips"][i])
        # Anchor to the cursor and flip toward the free side so the tooltip
        # never runs off the chart: left of the cursor near the right edge,
        # below it near the top (tall bars).
        w, h = self._canvas.get_width_height()
        left, below = event.x > w * 0.7, event.y > h * 0.65
        ann.xy = (event.xdata, event.ydata)
        ann.set_ha("right" if left else "left")
        ann.set_va("top" if below else "bottom")
        ann.xyann = (-14 if left else 14, -14 if below else 14)
        ann.set_visible(True)
        self._blitHover(data, True)
