"""Insights: where your shifts pay off. For a chosen range: headline
numbers, average take-home by weekday (chart), tables by shift type and by
section, and your best and slowest shifts."""
from datetime import timedelta

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import stats
from .. import charts, pages, widgets
from ..formatting import money

RANGES = ("Last 30 days", "Last 90 days", "This year", "All time")

TILES = (("net", "Take-home"), ("shifts", "Shifts"), ("per_shift", "Avg per shift"),
         ("per_hour", "Avg per hour"), ("hours", "Hours"), ("tip_out", "Tipped out"))

GROUP_HEADERS = ["Shifts", "Avg shift", "Per hour", "Total"]
SHIFT_HEADERS = ["Date", "Day", "Type", "Hours", "Take-home", "$/hr"]


class Insights(ttk.Frame):
    """"Insights" screen."""

    def __init__(self, master):
        super().__init__(master)
        self.app = master
        widgets.makeHeader(self, "Insights", master, backTo=pages.HOME)

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(0, 24))
        body.grid_columnconfigure(0, weight=3, uniform="ins")
        body.grid_columnconfigure(1, weight=2, uniform="ins")
        body.grid_rowconfigure(2, weight=1)

        # Range picker + tiles.
        bar = ttk.Frame(body)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(bar, text="Range", font=master.FONT_SMALL,
                  bootstyle="secondary").pack(side=LEFT, padx=(0, 6))
        self._range = ttk.StringVar(value=RANGES[1])
        box = ttk.Combobox(bar, textvariable=self._range, values=RANGES,
                           state="readonly", width=14, bootstyle="info")
        box.pack(side=LEFT)
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self._drawn = None  # (range, App.stamp()) of the last draw

        tiles = ttk.Frame(body)
        tiles.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self._tiles = {}
        for key, caption in TILES:
            tile, value = widgets.statTile(tiles, caption, master)
            tile.pack(side=LEFT, padx=(0, 10))
            self._tiles[key] = value

        # Left: weekday chart, best/worst shifts.
        left = ttk.Frame(body)
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=1)
        left.grid_rowconfigure(0, weight=1)
        self._chartHost = ttk.Frame(left)
        self._chartHost.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        self._fig = None
        self._canvas = None

        ttk.Label(left, text="\U0001F3C6  Best shifts", font=master.FONT_BOLD).grid(
            row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Label(left, text="\U0001F4C9  Slowest shifts", font=master.FONT_BOLD).grid(
            row=1, column=1, sticky="w", pady=(0, 6), padx=(10, 0))
        self.best = widgets.makeTable(left, SHIFT_HEADERS, height=5, bootstyle="success")
        self.best.grid(row=2, column=0, sticky="nsew")
        self.worst = widgets.makeTable(left, SHIFT_HEADERS, height=5, bootstyle="danger")
        self.worst.grid(row=2, column=1, sticky="nsew", padx=(10, 0))

        # Right: tables by weekday / shift type / section.
        right = ttk.Frame(body)
        right.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        self.groups = {}
        # (The weekday breakdown is the chart on the left.)
        self._groupCols = {"Type": "Shift Type", "Section": "Section"}
        for i, (key, title, h) in enumerate((("Type", "By shift type", 4),
                                              ("Section", "By section", 6))):
            ttk.Label(right, text=title, font=master.FONT_BOLD).grid(
                row=2 * i, column=0, sticky="w", pady=(0 if i == 0 else 16, 6))
            t = widgets.makeTable(right, [self._groupCols[key]] + GROUP_HEADERS,
                                  height=h, bootstyle="info")
            t.grid(row=2 * i + 1, column=0, sticky="nsew")
            self.groups[key] = t

        self.note = ttk.Label(body, text="", font=master.FONT_SMALL, bootstyle="secondary")
        self.note.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def onShow(self):
        self.refresh()

    def _bounds(self):
        today = self.app.today()
        r = self._range.get()
        if r == "Last 30 days":
            return today - timedelta(days=29), today
        if r == "Last 90 days":
            return today - timedelta(days=89), today
        if r == "This year":
            return today.replace(month=1, day=1), today
        return None, None

    def refresh(self):
        key = (self._range.get(), self.app.stamp())
        if key == self._drawn:
            return  # nothing changed since the last draw
        self._drawn = key
        d = stats.between(stats.shifts(self.app.logger.df), *self._bounds())
        t = stats.totals(d)
        for key, label in self._tiles.items():
            v = t[key]
            label.config(text=(str(v) if key == "shifts" else
                               f"{v:,.1f}" if key == "hours" else money(v)))

        for key, table in self.groups.items():
            g = stats.breakdown(d, key)
            widgets.loadTable(table, [self._groupCols[key]] + GROUP_HEADERS, [
                (r["Group"], str(int(r["Shifts"])), money(r["Avg shift"]),
                 money(r["Per hour"]) if r["Per hour"] == r["Per hour"] else "—",
                 money(r["Total"]))
                for _, r in g.iterrows()])

        for table, best in ((self.best, True), (self.worst, False)):
            widgets.loadTable(table, SHIFT_HEADERS, [
                (f"{r['Date']:%m/%d/%Y}", f"{r['Date']:%a}", r["Type"] or "—",
                 f"{r['Hours']:g}", money(r["Net"]),
                 money(r["Net"] / r["Hours"]) if r["Hours"] > 0 else "")
                for _, r in stats.ranked(d, 5, best).iterrows()])

        self._fig = charts.weekday_figure(stats.breakdown(d, "Weekday"), fig=self._fig)
        if self._canvas is None:
            self._canvas = FigureCanvasTkAgg(self._fig, master=self._chartHost)
            w = self._canvas.get_tk_widget()
            w.configure(bg=charts.BG, highlightthickness=0)
            w.pack(fill=BOTH, expand=YES)
        self._canvas.draw()

        untagged = int(((d["Type"] == "") & (d["Hours"] > 0)).sum())
        self.note.config(text=(
            f"{untagged} shift{'s' if untagged != 1 else ''} in this range "
            "have no shift type/section (logged before those existed) -- they count "
            "everywhere except the type and section tables." if untagged else ""))
