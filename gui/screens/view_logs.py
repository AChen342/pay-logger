"""View Logs: five tabs (Tips/Weekly/Monthly/Yearly/Payday) sharing one
searchable, paginated table. The Tips tab also has a Graph View (see
gui.tips_graph)."""
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from .. import formatting, pages, widgets
from ..tips_graph import TipsGraph

# Weekly/Monthly/Yearly tabs: (column holding the period, display format).
PERIOD_TABS = {
    "weekly":  ("Week Ending", "%m/%d/%Y"),
    "monthly": ("Month", "%m/%Y"),
    "yearly":  ("Year", "%Y"),
}


class ViewLogs(ttk.Frame):
    """"View Logs" screen. One Tableview is reused for all five tabs --
    each nav button just reloads it with a different DataFrame/headers."""

    TIP_HEADERS = formatting.TIP_HEADERS
    PAYDAY_HEADERS = ["Start", "End", "Hours", "Gross", "Tax", "Work Pay",
                       "Card", "Cash", "Tips", "Before Tax", "After Tax", "Hourly"]

    def __init__(self, master):
        super().__init__(master)
        widgets.makeHeader(self, "View Logs", master, backTo=pages.HOME)

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=32, pady=(0, 30))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self._kind = "tips"       # which tab is showing
        self._loaded = None       # (tab, App.stamp()) the table last showed
        self._graphMode = False   # table vs. graph (Tips tab only)

        nav = ttk.Frame(body)
        nav.grid(row=0, column=0, sticky="w", pady=(0, 14))
        for label, kind in (("Tips", "tips"), ("Weekly", "weekly"),
                            ("Monthly", "monthly"), ("Yearly", "yearly"),
                            ("Payday", "payday")):
            ttk.Button(nav, text=label, bootstyle="outline-info", width=12,
                       command=lambda k=kind: self._show(k)).pack(
                side=LEFT, padx=(0, 8), ipady=6)

        self.modeBtn = ttk.Button(body, text="", bootstyle="info", width=16,
                                  command=self.toggleMode)
        self.modeBtn.grid(row=0, column=1, sticky="e", pady=(0, 14))

        # The table and the graph share one grid cell; only one is shown.
        self.table = widgets.makeTable(
            body, self.TIP_HEADERS, height=18,
            searchable=True, paginated=True, pagesize=15, bootstyle="info"
        )
        self.table.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.graph = TipsGraph(body, master)
        self.graph.grid(row=1, column=0, columnspan=2, sticky="nsew")

        ttk.Button(body, text="← Back to Home", bootstyle="secondary-outline",
                   command=lambda: master.showFrame(pages.HOME)).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(20, 0))

        self._setGraphMode(False)
        self._show("tips")

    def onShow(self):
        """Reload the current tab each time the screen is shown, so logs
        added on other screens show up."""
        if self._graphMode:
            self.graph.refresh(onlyIfChanged=True)
        else:
            self._loadTable()

    # --- Tabs ---------------------------------------------------------
    def _show(self, kind):
        """Switch tabs. Graph View exists only for Tips, so any other tab
        drops back to its table and hides the toggle."""
        self._kind = kind
        if kind == "tips":
            self.modeBtn.grid()
        else:
            self.modeBtn.grid_remove()
            self._setGraphMode(False)
        if self._graphMode:
            self.graph.refresh(onlyIfChanged=True)
        else:
            self._loadTable()

    def toggleMode(self):
        self._setGraphMode(not self._graphMode)
        if self._graphMode:
            self.graph.refresh(onlyIfChanged=True)  # redraw only if logs changed
        else:
            self._loadTable()

    def _setGraphMode(self, on):
        """Show either the graph or the table, and label the toggle with
        the view it will switch to."""
        self._graphMode = on
        if on:
            self.table.grid_remove()
            self.graph.grid()
            self.modeBtn.configure(text="\U0001F4CB  Table View")
        else:
            self.graph.grid_remove()
            self.table.grid()
            self.modeBtn.configure(text="\U0001F4C8  Graph View")

    def _loadTable(self):
        """Fill the table for the current tab, most recent row first."""
        lg = self.master.logger
        kind = self._kind
        key = (kind, self.master.stamp())
        if key == self._loaded:
            return  # already showing exactly this
        self._loaded = key
        if kind == "tips":
            headers, rows = self.TIP_HEADERS, formatting.tip_rows(lg.df[::-1])
        elif kind == "payday":
            headers, rows = self.PAYDAY_HEADERS, formatting.payday_rows(lg.dfPayDay[::-1])
        else:
            col, fmt = PERIOD_TABS[kind]
            df = {"weekly": lg.dfWeekly, "monthly": lg.dfMonthly, "yearly": lg.dfYearly}[kind]
            headers = [col, "Hours", "Card", "Cash", "Take-home"]
            rows = formatting.period_rows(df[::-1], col, fmt)
        widgets.loadTable(self.table, headers, rows)
